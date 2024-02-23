import multiprocessing
from logging import Logger
from multiprocessing import Process
from typing import Any
from blueprints_ng.blueprint_ng import BlueprintNG
from blueprints_ng.lcm.blueprint_route_manager import get_function_to_be_called
from models.blueprint_ng.worker_message import WorkerMessageType, WorkerMessage
from utils.log import create_logger
logger: Logger = create_logger('BLUELCMWORKER_BETA')


class BlueprintWorker:
    blueprint: BlueprintNG
    message_queue: multiprocessing.Queue
    process: Process = None

    def __init__(self, blueprint: BlueprintNG):
        self.blueprint = blueprint
        self.message_queue = multiprocessing.Queue()

    def start_listening(self):
        self.process = Process(target=self._listen, args=())
        self.process.start()

    def stop_listening(self):
        # TODO check stop from outside
        self.process.close()

    def put_message(self, msg_type: WorkerMessageType, path: str, message: Any):
        """
        Insert the worker message into the queue. This function should be called by an external process to the worker.
        THREAD SAFE.

        Args:
            msg_type: The type of the message (DAY0 (creation), DAY2, STOP)
            path: The path of the request.
            message: The message of the request.
        """
        worker_message = WorkerMessage(message_type=msg_type, message=message, path=path)
        self.message_queue.put(worker_message) # Thread safe

    def destroy_blueprint(self):
        """
        Sent a termination message to the worker. This function should be called by an external process to the worker.
        """
        worker_message = WorkerMessage(message_type=WorkerMessageType.STOP, message="", path="")
        self.message_queue.put(worker_message)  # Thread safe

    def _listen(self):
        logger.debug(f"Worker for blueprint: {self.blueprint.base_model.id} is listening.")
        while True:
            received_message: WorkerMessage = self.message_queue.get() # Thread safe
            logger.debug(f"MSG for blueprint {self.blueprint.base_model.id}: {received_message.message}")
            match received_message.message_type:
                case WorkerMessageType.DAY0:
                    # This is the case of blueprint creation (create and start VMs, Dockers, ...)
                    self.blueprint.create(received_message.message)
                case WorkerMessageType.DAY2:
                    # This is the DAY2 message, getting the function to be called
                    function = get_function_to_be_called(received_message.path)
                    # Starting processing the request.
                    result = getattr(self.blueprint, function)(received_message.message)
                case WorkerMessageType.STOP:
                    self.blueprint.destroy()
                    self.stop_listening()
                case _:
                    raise ValueError("Worker message type not recognized")

            logger.debug(f"Received message for blue {self.blueprint.base_model.id}: {received_message}")

    def __eq__(self, __value):
        """
        Allow finding duplicate workers. Two workers are equivalent if built on the same blueprint (if blue.id is the same)
        Args:
            __value: (BlueprintWorker) The object to be compared
        """
        if isinstance(__value, BlueprintWorker):
            if self.blueprint.base_model.id == __value.blueprint.base_model.id:
                return True
        return False

