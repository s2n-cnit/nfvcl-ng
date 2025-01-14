from queue import Queue
from threading import Thread

from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.models.task import NFVCLTask, NFVCLTaskResult


class TaskManager(GenericManager):
    def __init__(self, worker_count: int):
        super().__init__()
        self.queue: Queue = Queue()
        self.worker_count = worker_count
        self.worker_list = []
        self.start_workers()

    def start_workers(self):
        for i in range(0, self.worker_count):
            thread = Thread(target=self.worker, daemon=True, name=f"Worker-{i}")
            self.worker_list.append(thread)
            thread.start()

    def stop_workers(self):
        # TODO: Implement
        pass

    def add_task(self, task: NFVCLTask):
        self.queue.put(task)

    def worker(self):
        while True:
            task: NFVCLTask = self.queue.get()
            self.logger.verbose(f'Working on {task}')
            excep = None
            try:
                returnof = task.callable_function(*task.args, **task.kwargs)
            except Exception as e:
                self.logger.error(f'Error on {task}: {e}', exc_info=e)
                returnof = None
                excep = e


            self.logger.verbose(f'Finished {task}')
            self.queue.task_done()
            if task.callback_function:
                task.callback_function(NFVCLTaskResult(returnof, excep is not None ,excep))
