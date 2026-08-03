from threading import Event

from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core.managers.task_manager import TaskManager
from nfvcl_core_models.response_model import AsyncTaskResponse, AsyncTaskStatus
from nfvcl_core_models.task import NFVCLTask, NFVCLTaskStatusType


class FakeBlueprintManager:
    def __init__(self):
        self.released_blueprint_ids = []

    def precheck_create_blueprint(self, path, msg):
        return AsyncTaskResponse(blueprint_id="BLUE01", status=AsyncTaskStatus.deploying, detail="Blueprint BLUE01 is being deployed...")

    def release_reserved_blueprint_id(self, blueprint_id):
        self.released_blueprint_ids.append(blueprint_id)

    def create_blueprint(self, path, msg, blueprint_id=None):
        return blueprint_id


class FailingBlueprintManager(FakeBlueprintManager):
    def precheck_create_blueprint(self, path, msg):
        return AsyncTaskResponse(status=AsyncTaskStatus.failed, detail="precheck failed")


def test_delete_queued_task_removes_not_started_task():
    task_manager = TaskManager(worker_count=0)
    task = NFVCLTask(lambda: "done", None)

    task_manager.add_task(task)

    task_status = task_manager.get_task_status(task.task_id)
    assert task_status is not None
    assert task_status.status == NFVCLTaskStatusType.QUEUED
    assert [active_task.task_id for active_task in task_manager.list_queued_running_tasks()] == [task.task_id]

    assert task_manager.delete_queued_task(task.task_id) is True
    assert task_manager.get_task_status(task.task_id) is None
    assert task_manager.list_queued_running_tasks() == []
    assert task_manager.queue.empty()


def test_delete_running_task_is_rejected():
    started = Event()
    finish = Event()

    def wait_until_released():
        started.set()
        finish.wait(timeout=2)

    task_manager = TaskManager(worker_count=1)
    task = NFVCLTask(wait_until_released, None)

    task_manager.add_task(task)
    assert started.wait(timeout=2)

    task_status = task_manager.get_task_status(task.task_id)
    assert task_status is not None
    assert task_status.status == NFVCLTaskStatusType.RUNNING
    assert task_manager.delete_queued_task(task.task_id) is False

    finish.set()
    task_manager.queue.join()



def test_create_blueprint_precheck_response_is_returned_without_worker():
    nfvcl = NFVCL.__new__(NFVCL)
    nfvcl.task_manager = TaskManager(worker_count=0)
    nfvcl.blueprint_manager = FakeBlueprintManager()

    async_response = nfvcl.create_blueprint("fake", object(), callback=lambda result: None)

    assert async_response.status == AsyncTaskStatus.deploying
    assert async_response.blueprint_id == "BLUE01"
    assert async_response.task_id is not None
    assert nfvcl.task_manager.get_task_status(async_response.task_id).status == NFVCLTaskStatusType.QUEUED
    queued_task = nfvcl.task_manager.task_history[async_response.task_id].task
    assert queued_task.kwargs["blueprint_id"] == "BLUE01"
    assert "_on_cancel" not in queued_task.kwargs

    assert nfvcl.task_manager.delete_queued_task(async_response.task_id) is True
    assert nfvcl.blueprint_manager.released_blueprint_ids == ["BLUE01"]


def test_failed_create_blueprint_precheck_does_not_enqueue_task():
    nfvcl = NFVCL.__new__(NFVCL)
    nfvcl.task_manager = TaskManager(worker_count=0)
    nfvcl.blueprint_manager = FailingBlueprintManager()

    async_response = nfvcl.create_blueprint("fake", object(), callback=lambda result: None)

    assert async_response.status == AsyncTaskStatus.failed
    assert async_response.detail == "precheck failed"
    assert async_response.task_id is None
    assert nfvcl.task_manager.list_queued_running_tasks() == []
