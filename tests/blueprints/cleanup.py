from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core_models.custom_types import NFVCLCoreException

CORE_BLUEPRINT_TYPES = {
    "sdcore",
    "free5gc",
    "oai",
    "open5gs",
    "athonet",
    "amarisoft",
}


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def _get_k8s_clusters(nfvcl: NFVCL):
    try:
        return nfvcl.get_kubernetes_list()
    except NFVCLCoreException as exc:
        if exc.http_equivalent_code == 404:
            return []
        raise


def _cleanup_priority(blueprint, deployed_blueprint_ids: set[str], blocked_k8s_ids: set[str]) -> tuple[int, str, str]:
    blue_type = blueprint.base_model.type
    if blueprint.id in deployed_blueprint_ids:
        return 0, blue_type, blueprint.id
    if blue_type in CORE_BLUEPRINT_TYPES:
        return 1, blue_type, blueprint.id
    if blue_type == "k8s":
        if blueprint.id in blocked_k8s_ids:
            return 4, blue_type, blueprint.id
        return 2, blue_type, blueprint.id
    if blue_type == "ueransim":
        return 3, blue_type, blueprint.id
    return 3, blue_type, blueprint.id


def delete_remaining_blueprints(nfvcl: NFVCL) -> None:
    errors: list[tuple[str, Exception]] = []

    while True:
        blueprints = list(nfvcl.blueprint_manager.get_blueprint_instances())
        if not blueprints:
            break

        blueprint_ids_before = {blueprint.id for blueprint in blueprints}
        deployed_blueprint_ids, blocked_k8s_ids = _get_k8s_cleanup_dependencies(
            nfvcl,
            blueprint_ids_before,
        )
        root_blueprints = [
            blueprint
            for blueprint in blueprints
            if blueprint.base_model.parent_blue_id is None
        ]
        deployed_blueprints = [
            blueprint
            for blueprint in blueprints
            if blueprint.id in deployed_blueprint_ids
        ]
        blueprint_candidates = {
            blueprint.id: blueprint
            for blueprint in [*deployed_blueprints, *(root_blueprints or blueprints)]
        }
        blueprints_to_delete = sorted(
            blueprint_candidates.values(),
            key=lambda blueprint: _cleanup_priority(
                blueprint,
                deployed_blueprint_ids,
                blocked_k8s_ids,
            ),
        )

        for blueprint in blueprints_to_delete:
            if blueprint.id in blocked_k8s_ids:
                continue
            if (
                blocked_k8s_ids
                and blueprint.id not in deployed_blueprint_ids
                and blueprint.base_model.type not in CORE_BLUEPRINT_TYPES
            ):
                continue
            try:
                nfvcl.blueprint_manager.delete_blueprint(
                    blueprint.id,
                    child_deletion=blueprint.base_model.parent_blue_id is not None,
                )
            except Exception as exc:  # noqa: BLE001
                if _is_not_found(exc):
                    continue
                errors.append((blueprint.id, exc))

        if errors:
            break

        blueprint_ids_after = {
            blueprint.id
            for blueprint in nfvcl.blueprint_manager.get_blueprint_instances()
        }
        if blueprint_ids_after == blueprint_ids_before:
            details = ", ".join(sorted(blueprint_ids_after))
            raise AssertionError(f"Failed to delete test blueprints, no cleanup progress for: {details}")

    _raise_cleanup_errors(errors)


def _get_k8s_cleanup_dependencies(nfvcl: NFVCL, existing_blueprint_ids: set[str]) -> tuple[set[str], set[str]]:
    deployed_blueprint_ids: set[str] = set()
    blocked_k8s_ids: set[str] = set()

    for cluster in _get_k8s_clusters(nfvcl):
        active_deployed_blueprints = [
            blueprint_id
            for blueprint_id in cluster.deployed_blueprints
            if blueprint_id in existing_blueprint_ids
        ]
        stale_deployed_blueprints = [
            blueprint_id
            for blueprint_id in cluster.deployed_blueprints
            if blueprint_id not in existing_blueprint_ids
        ]

        if stale_deployed_blueprints:
            cluster.deployed_blueprints = active_deployed_blueprints
            nfvcl.update_kubernetes(cluster)

        deployed_blueprint_ids.update(active_deployed_blueprints)
        if active_deployed_blueprints:
            blocked_k8s_ids.add(cluster.blueprint_ref or cluster.name)

    return deployed_blueprint_ids, blocked_k8s_ids


def _raise_cleanup_errors(errors: list[tuple[str, Exception]]) -> None:
    if not errors:
        return

    details = "; ".join(f"{blueprint_id}: {exc}" for blueprint_id, exc in errors)
    raise AssertionError(f"Failed to delete test blueprints: {details}") from errors[0][1]
