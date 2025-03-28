from queue import Queue
from threading import Thread
from typing import Dict, Optional

from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core_models.task import NFVCLTask, NFVCLTaskResult


class TaskHistoryElement:
    def __init__(self, task_id: str, task: NFVCLTask, result: Optional[NFVCLTaskResult] = None):
        self.task_id = task_id
        self.task = task
        self.result = result

class TaskManager(GenericManager):
    def __init__(self, worker_count: int):
        super().__init__()
        self.queue: Queue = Queue()
        self.worker_count = worker_count
        self.worker_list = []
        self.task_history: Dict[str, TaskHistoryElement] = {}
        self.start_workers()

    def start_workers(self):
        for i in range(0, self.worker_count):
            thread = Thread(target=self.worker, daemon=True, name=f"Worker-{i}")
            self.worker_list.append(thread)
            thread.start()

    def stop_workers(self):
        # TODO: Implement
        pass

    def add_task(self, task: NFVCLTask) -> str:
        self.queue.put(task)
        return task.task_id

    def worker(self):
        while True:
            task: NFVCLTask = self.queue.get()
            self.task_history[task.task_id] = TaskHistoryElement(task_id=task.task_id, task=task)
            self.logger.spam(f'Working on {task}')
            excep = None
            try:
                returnof = task.callable_function(*task.args, **task.kwargs)
            except Exception as e:
                self.logger.error(f'Error on {task}: {e}', exc_info=e)
                returnof = None
                excep = e

            self.logger.spam(f'Finished {task}')
            self.queue.task_done()

            task_result = NFVCLTaskResult(task.task_id, returnof, excep is not None, excep)
            self.task_history[task.task_id].result = task_result

            if task.callback_function:
                task.callback_function(task_result)
