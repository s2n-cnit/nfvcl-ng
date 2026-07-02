from queue import Queue
from threading import Lock, Thread
from typing import Dict, List, Optional

from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core_models.pre_work import PreWorkCallbackResponse
from nfvcl_core_models.response_model import OssCompliantResponse, OssStatus
from nfvcl_core_models.task import NFVCLTask, NFVCLTaskResult, NFVCLTaskStatus, NFVCLTaskStatusType


class TaskHistoryElement:
    def __init__(self, task_id: str, task: NFVCLTask, result: Optional[NFVCLTaskResult] = None, started: bool = False):
        self.task_id = task_id
        self.task = task
        self.result = result
        self.started = started

class TaskManager(GenericManager):
    def __init__(self, worker_count: int):
        super().__init__()
        self.queue: Queue = Queue()
        self.worker_count = worker_count
        self.worker_list = []
        self.task_history: Dict[str, TaskHistoryElement] = {}
        self._task_lock = Lock()
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
        with self._task_lock:
            self.task_history[task.task_id] = TaskHistoryElement(task_id=task.task_id, task=task)
            self.queue.put(task)
        return task.task_id

    def get_task_status(self, task_id: str) -> Optional[NFVCLTaskStatus]:
        with self._task_lock:
            task_history_element = self.task_history.get(task_id)
            if task_history_element is None:
                return None
            return self._task_history_element_to_status(task_history_element)

    def list_queued_running_tasks(self) -> List[NFVCLTaskStatus]:
        with self._task_lock:
            return [
                self._task_history_element_to_status(task_history_element)
                for task_history_element in self.task_history.values()
                if task_history_element.result is None
            ]

    def delete_queued_task(self, task_id: str) -> Optional[bool]:
        pre_work_callback = None
        with self._task_lock:
            task_history_element = self.task_history.get(task_id)
            if task_history_element is None:
                return None
            if task_history_element.started or task_history_element.result is not None:
                return False
            if not self._remove_task_from_queue(task_id):
                return False
            pre_work_callback = task_history_element.task.kwargs.get("pre_work_callback")
            del self.task_history[task_id]
        if pre_work_callback:
            pre_work_callback(PreWorkCallbackResponse(async_return=OssCompliantResponse(status=OssStatus.failed, detail=f"Task {task_id} deleted before it started")))
        return True

    @staticmethod
    def _task_history_element_to_status(task_history_element: TaskHistoryElement) -> NFVCLTaskStatus:
        if task_history_element.result is None:
            status = NFVCLTaskStatusType.RUNNING if task_history_element.started else NFVCLTaskStatusType.QUEUED
            return NFVCLTaskStatus(task_id=task_history_element.task_id, status=status)
        return NFVCLTaskStatus(
            task_id=task_history_element.task_id,
            status=NFVCLTaskStatusType.DONE,
            result=task_history_element.result.result,
            error=task_history_element.result.error,
            exception=str(task_history_element.result.exception) if task_history_element.result.exception else None,
        )

    def _remove_task_from_queue(self, task_id: str) -> bool:
        with self.queue.mutex:
            for queued_task in self.queue.queue:
                if queued_task.task_id == task_id:
                    self.queue.queue.remove(queued_task)
                    self.queue.unfinished_tasks -= 1
                    if self.queue.unfinished_tasks == 0:
                        self.queue.all_tasks_done.notify_all()
                    self.queue.not_full.notify()
                    return True
        return False

    def worker(self):
        while True:
            task: NFVCLTask = self.queue.get()
            with self._task_lock:
                task_history_element = self.task_history.get(task.task_id)
                if task_history_element is None:
                    self.queue.task_done()
                    continue
                task_history_element.started = True
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
            with self._task_lock:
                self.task_history[task.task_id].result = task_result

            if task.callback_function:
                task.callback_function(task_result)
