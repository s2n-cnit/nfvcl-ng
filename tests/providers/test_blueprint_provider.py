from nfvcl_core_models.http_models import BlueprintNotFoundException
from nfvcl_providers.blueprint.blueprint_provider import BlueprintProvider
from tests.providers.fakes import SaveSpy


class FakeBlueprintManager:
    def __init__(self):
        self.created: list[tuple[str, object, str]] = []
        self.deleted: list[tuple[str, bool]] = []
        self.calls: list[tuple[str, str, tuple, dict]] = []
        self.missing_blueprints: set[str] = set()

    def create_blueprint(self, path: str, msg: object, parent_id: str | None = None) -> str:
        self.created.append((path, msg, parent_id))
        return f"{parent_id}-child"

    def delete_blueprint(self, blueprint_id: str, child_deletion: bool = False) -> None:
        if blueprint_id in self.missing_blueprints:
            raise BlueprintNotFoundException(blueprint_id)
        self.deleted.append((blueprint_id, child_deletion))

    def call_function(self, blue_id: str, function_name: str, *args, **kwargs) -> object:
        self.calls.append((blue_id, function_name, args, kwargs))
        return {"ok": True}


def test_blueprint_provider_tracks_created_and_deleted_children():
    manager = FakeBlueprintManager()
    save = SaveSpy()
    provider = BlueprintProvider(manager, persistence_function=save)

    child_id = provider.create_blueprint("child/path", {"payload": True}, parent_id="parent")

    assert child_id == "parent-child"
    assert provider.data.get_child_blueprints("parent") == ["parent-child"]
    assert manager.created == [("child/path", {"payload": True}, "parent")]
    assert save.calls == 1

    deleted_id = provider.delete_blueprint("parent-child", parent_id="parent")

    assert deleted_id == "parent-child"
    assert provider.data.get_child_blueprints("parent") == []
    assert manager.deleted == [("parent-child", True)]
    assert save.calls == 2


def test_blueprint_provider_cleanup_deletes_leftover_children_and_clears_state():
    manager = FakeBlueprintManager()
    save = SaveSpy()
    provider = BlueprintProvider(manager, persistence_function=save)
    provider.data.add_child_blueprint("parent", "child-a")
    provider.data.add_child_blueprint("parent", "child-b")
    manager.missing_blueprints.add("child-b")

    provider.cleanup_resource_group("parent")

    assert manager.deleted == [("child-a", True)]
    assert provider.data.get_child_blueprints("parent") == []
    assert save.calls == 1


def test_blueprint_provider_delegates_day2_calls():
    manager = FakeBlueprintManager()
    provider = BlueprintProvider(manager)

    result = provider.call_blueprint_function("blue-id", "restart", "arg", force=True)

    assert result == {"ok": True}
    assert manager.calls == [("blue-id", "restart", ("arg",), {"force": True})]
