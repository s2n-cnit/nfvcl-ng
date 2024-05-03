import queue
import threading
from functools import partial
from threading import Thread
from typing import Any

from blueprints_ng.blueprint_ng import BlueprintNG, BlueprintNGStatus, CurrentOperation
from blueprints_ng.lcm.blueprint_route_manager import get_function_to_be_called
from models.blueprint_ng.worker_message import WorkerMessageType, WorkerMessage
from utils.log import create_logger

# multiprocessing_manager = multiprocessing.Manager()


def callback_function(event, namespace, msg):
    namespace["msg"] = msg
    event.set()


class BlueprintWorker:
    blueprint: BlueprintNG
    message_queue: queue.Queue
    thread: Thread = None

    def __init__(self, blueprint: BlueprintNG):
        self.blueprint = blueprint
        self.logger = create_logger('BLUEV2_WORKER', blueprintid=blueprint.id)
        self.message_queue = queue.Queue()

    def start_listening(self):
        self.thread = Thread(target=self._listen, args=())
        self.thread.start()

    def stop_listening(self):
        # TODO kill thread and check if stop from outside
        self.logger.info("Blueprint worker stopping listening.")

    def call_function_sync(self, function_name, *args, **kwargs):
        """
        Call a function synchronously
        Args:
            function_name: Name of the function to call
            *args: args
            **kwargs: kwargs

        Returns: return value of the function
        """
        # used to wait for the call to be completed
        event = threading.Event()
        # used to receive the return data from the function
        namespace = {}

        self.put_message(WorkerMessageType.DAY2_BY_NAME, function_name, (args, kwargs), callback=partial(callback_function, event, namespace))
        event.wait()

        return namespace["msg"]

    def put_message_sync(self, msg_type: WorkerMessageType, path: str, message: Any):
        # used to wait for the call to be completed
        event = threading.Event()
        # used to receive the return data from the function
        namespace = {}

        self.put_message(msg_type, path, message, callback=partial(callback_function, event, namespace))
        event.wait()

        return namespace["msg"]

    def put_message(self, msg_type: WorkerMessageType, path: str, message: Any, callback: callable = None):
        """
        Insert the worker message into the queue. This function should be called by an external process to the worker.
        THREAD SAFE.

        Args:
            msg_type: The type of the message (DAY0 (creation), DAY2, STOP)
            path: The path of the request.
            message: The message of the request.
            callback: Function to be called after the message is processed
        """
        worker_message = WorkerMessage(message_type=msg_type, message=message, path=path, callback=callback)
        self.message_queue.put(worker_message)  # Thread safe

    def destroy_blueprint_sync(self):
        """
        Sent a termination message to the worker. This function should be called by an external process to the worker.
        """
        self.put_message_sync(WorkerMessageType.STOP, message="", path="")

    def destroy_blueprint(self):
        """
        Sent a termination message to the worker. This function should be called by an external process to the worker.
        """
        worker_message = WorkerMessage(message_type=WorkerMessageType.STOP, message="", path="")
        self.message_queue.put(worker_message)  # Thread safe

    def _listen(self):
        self.logger.debug(f"Worker listening")
        while True:
            received_message: WorkerMessage = self.message_queue.get()  # Thread safe
            self.logger.debug(f"Received message: {received_message.message}")
            match received_message.message_type:
                case WorkerMessageType.DAY0:
                    # This is the case of blueprint creation (create and start VMs, Dockers, ...)
                    self.logger.info(f"Creating blueprint")
                    try:
                        self.blueprint.base_model.status = BlueprintNGStatus.deploying(self.blueprint.id)
                        self.blueprint.create(received_message.message)
                        if received_message.callback:
                            received_message.callback(self.blueprint.id)
                        self.blueprint.base_model.status = BlueprintNGStatus(current_operation=CurrentOperation.IDLE)
                        self.logger.success(f"Blueprint created")
                    except Exception as e:
                        self.blueprint.base_model.status.error = True
                        self.blueprint.base_model.status.detail = str(e)
                        self.logger.error(f"Error creating blueprint", exc_info=e)
                    self.blueprint.to_db()
                case WorkerMessageType.DAY2 | WorkerMessageType.DAY2_BY_NAME:
                    self.logger.info(f"Calling function on blueprint")
                    # This is the DAY2 message, getting the function to be called
                    self.blueprint.base_model.status = BlueprintNGStatus(current_operation=CurrentOperation.RUNNING_DAY2_OP, detail=f"Calling function {received_message.path} on blueprint {self.blueprint.id}")
                    try:
                        if received_message.message_type == WorkerMessageType.DAY2:
                            function = get_function_to_be_called(received_message.path)
                            result = getattr(self.blueprint, function)(received_message.message)
                        else:
                            result = getattr(self.blueprint, received_message.path)(*received_message.message[0], **received_message.message[1])
                        # Starting processing the request.
                        if received_message.callback:
                            received_message.callback(result)
                        self.blueprint.base_model.status = BlueprintNGStatus(current_operation=CurrentOperation.IDLE)
                        self.logger.success(f"Function called on blueprint")
                    except Exception as e:
                        self.blueprint.base_model.status.error = True
                        self.blueprint.base_model.status.detail = str(e)
                        self.logger.error(f"Error calling function on blueprint", exc_info=e)
                    self.blueprint.to_db()
                case WorkerMessageType.STOP:
                    self.logger.info(f"Destroying blueprint")
                    self.blueprint.base_model.status = BlueprintNGStatus.destroying(blue_id=self.blueprint.id)
                    self.blueprint.destroy()
                    if received_message.callback:
                        received_message.callback(self.blueprint.id)
                    self.logger.success(f"Blueprint destroyed")
                    break
                case _:
                    raise ValueError("Worker message type not recognized")

        self.stop_listening()

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
