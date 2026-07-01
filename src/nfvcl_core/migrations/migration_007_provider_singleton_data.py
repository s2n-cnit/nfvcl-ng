from __future__ import annotations

from copy import deepcopy
from typing import Any

from pymongo.synchronous.database import Database

from nfvcl_common.utils.log import create_logger
from nfvcl_core.migrations.base_class_migration import Migration


OPENSTACK_PROVIDER_TYPE = "openstack"
PROXMOX_PROVIDER_TYPE = "proxmox"
EXTERNAL_REST_PROVIDER_TYPE = "external_rest"
KUBERNETES_PROVIDER_TYPE = "kubernetes"
PDU_PROVIDER_TYPE = "pdu"
BLUEPRINT_PROVIDER_TYPE = "blueprint"
DIAGNOSTIC_PROVIDER_TYPE = "diagnostic"
RESOURCE_TYPES_WITH_RESOURCE_GROUP = {"ResourceDeployable", "ResourceConfiguration"}


class Migration007ProviderSingletonData(Migration):
    def __init__(self):
        self.logger = create_logger("Migration007ProviderSingletonData")

    def upgrade(self, db: Database) -> None:
        providers_collection = db["providers"]
        legacy_provider_docs = list(providers_collection.find({
            "blueprint_id": {"$exists": True},
            "provider_type": {"$exists": False},
        }))

        self._migrate_blueprint_resource_groups(db)

        if not legacy_provider_docs:
            self.logger.info("No legacy blueprint-scoped provider documents found")
            return

        vim_info_by_area = self._get_vim_info_by_area(db)
        provider_data_by_type = self._load_existing_singleton_provider_data(db)
        touched_provider_types: set[str] = set()

        for legacy_doc in legacy_provider_docs:
            blueprint_id = legacy_doc.get("blueprint_id")
            if not blueprint_id:
                self.logger.warning(f"Skipping provider document without blueprint_id: {legacy_doc.get('_id')}")
                continue

            self._migrate_virtualization_data(
                legacy_doc=legacy_doc,
                blueprint_id=blueprint_id,
                vim_info_by_area=vim_info_by_area,
                provider_data_by_type=provider_data_by_type,
                touched_provider_types=touched_provider_types,
            )
            self._migrate_kubernetes_data(
                legacy_doc=legacy_doc,
                blueprint_id=blueprint_id,
                provider_data_by_type=provider_data_by_type,
                touched_provider_types=touched_provider_types,
            )
            self._migrate_pdu_data(
                legacy_doc=legacy_doc,
                blueprint_id=blueprint_id,
                provider_data_by_type=provider_data_by_type,
                touched_provider_types=touched_provider_types,
            )
            self._migrate_blueprint_data(
                legacy_doc=legacy_doc,
                blueprint_id=blueprint_id,
                provider_data_by_type=provider_data_by_type,
                touched_provider_types=touched_provider_types,
            )
            self._migrate_diagnostic_data(
                legacy_doc=legacy_doc,
                blueprint_id=blueprint_id,
                provider_data_by_type=provider_data_by_type,
                touched_provider_types=touched_provider_types,
            )

        for provider_type in touched_provider_types:
            providers_collection.update_one(
                {"provider_type": provider_type},
                {
                    "$set": {
                        "provider_type": provider_type,
                        "data": provider_data_by_type[provider_type],
                    },
                },
                upsert=True,
            )

        providers_collection.delete_many({
            "_id": {"$in": [doc["_id"] for doc in legacy_provider_docs]},
        })
        self.logger.info(
            f"Migrated {len(legacy_provider_docs)} legacy provider documents into "
            f"{len(touched_provider_types)} singleton provider documents"
        )

    def downgrade(self, db: Database) -> None:
        pass

    def _migrate_blueprint_resource_groups(self, db: Database) -> None:
        blueprint_docs_updated = 0
        registered_resources_updated = 0
        nested_resources_updated = 0
        state_resources_updated = 0

        for blueprint_doc in db["blueprints"].find():
            blueprint_id = blueprint_doc.get("id")
            if not blueprint_id:
                self.logger.warning(f"Skipping blueprint document without id: {blueprint_doc.get('_id')}")
                continue

            update_fields = {}

            registered_resources = blueprint_doc.get("registered_resources") or {}
            if registered_resources and not isinstance(registered_resources, dict):
                self.logger.warning(f"Skipping invalid registered_resources for blueprint {blueprint_id}")
            elif isinstance(registered_resources, dict):
                updated_registered_resources = deepcopy(registered_resources)
                blueprint_registered_resources_updated = 0
                blueprint_nested_resources_updated = 0

                for registered_resource in updated_registered_resources.values():
                    if not isinstance(registered_resource, dict):
                        continue

                    resource_value = registered_resource.get("value")
                    if not isinstance(resource_value, dict):
                        continue

                    if resource_value.get("resource_group") != blueprint_id:
                        resource_value["resource_group"] = blueprint_id
                        blueprint_registered_resources_updated += 1

                    blueprint_nested_resources_updated += self._set_resource_group_on_nested_resources(
                        obj=resource_value,
                        resource_group=blueprint_id,
                        skip_root=True,
                    )

                if blueprint_registered_resources_updated or blueprint_nested_resources_updated:
                    update_fields["registered_resources"] = updated_registered_resources
                    registered_resources_updated += blueprint_registered_resources_updated
                    nested_resources_updated += blueprint_nested_resources_updated

            state = blueprint_doc.get("state")
            if isinstance(state, dict | list):
                updated_state = deepcopy(state)
                blueprint_state_resources_updated = self._set_resource_group_on_nested_resources(
                    obj=updated_state,
                    resource_group=blueprint_id,
                )
                if blueprint_state_resources_updated:
                    update_fields["state"] = updated_state
                    state_resources_updated += blueprint_state_resources_updated
            elif state is not None:
                self.logger.warning(f"Skipping invalid state for blueprint {blueprint_id}")

            if update_fields:
                db["blueprints"].update_one(
                    {"_id": blueprint_doc["_id"]},
                    {"$set": update_fields},
                )
                blueprint_docs_updated += 1

        self.logger.info(
            f"Updated resource_group on {registered_resources_updated} registered resources, "
            f"{nested_resources_updated} nested registered resources, and {state_resources_updated} state resources "
            f"in {blueprint_docs_updated} blueprint documents"
        )

    def _set_resource_group_on_nested_resources(
        self,
        obj: Any,
        resource_group: str,
        skip_root: bool = False,
    ) -> int:
        updated_resources = 0

        if isinstance(obj, dict):
            is_resource_dict = obj.get("type") in RESOURCE_TYPES_WITH_RESOURCE_GROUP
            if is_resource_dict and not skip_root and obj.get("resource_group") != resource_group:
                obj["resource_group"] = resource_group
                updated_resources += 1

            for value in obj.values():
                updated_resources += self._set_resource_group_on_nested_resources(
                    obj=value,
                    resource_group=resource_group,
                )

        if isinstance(obj, list):
            for item in obj:
                updated_resources += self._set_resource_group_on_nested_resources(
                    obj=item,
                    resource_group=resource_group,
                )

        return updated_resources

    def _load_existing_singleton_provider_data(self, db: Database) -> dict[str, dict]:
        provider_data_by_type: dict[str, dict] = {}
        for provider_doc in db["providers"].find({"provider_type": {"$exists": True}}):
            provider_type = provider_doc.get("provider_type")
            if provider_type:
                provider_data_by_type[provider_type] = deepcopy(provider_doc.get("data") or {})
        return provider_data_by_type

    def _get_vim_info_by_area(self, db: Database) -> dict[str, dict[str, str]]:
        vim_info_by_area: dict[str, dict[str, str]] = {}
        for topology_doc in db["topology"].find():
            for vim in topology_doc.get("vims", []):
                vim_name = vim.get("name")
                vim_type = vim.get("vim_type")
                if not vim_name or not vim_type:
                    continue
                for area in vim.get("areas", []):
                    vim_info_by_area[str(area)] = {
                        "vim_name": vim_name,
                        "vim_type": vim_type,
                    }
        return vim_info_by_area

    def _migrate_virtualization_data(
        self,
        legacy_doc: dict[str, Any],
        blueprint_id: str,
        vim_info_by_area: dict[str, dict[str, str]],
        provider_data_by_type: dict[str, dict],
        touched_provider_types: set[str],
    ) -> None:
        for area, legacy_provider in (legacy_doc.get("virtualization") or {}).items():
            provider_data = self._extract_provider_data(legacy_provider)

            area_vim_info = vim_info_by_area.get(str(area), {})
            provider_type = self._get_virtualization_provider_type(
                legacy_provider,
                area_vim_info.get("vim_type"),
            )
            if provider_type is None:
                self.logger.warning(
                    f"Cannot infer virtualization provider type for blueprint {blueprint_id}, area {area}"
                )
                continue

            if not provider_data and provider_type != EXTERNAL_REST_PROVIDER_TYPE:
                continue

            provider_type_data = provider_data_by_type.setdefault(provider_type, {})
            touched_provider_types.add(provider_type)

            if "vims" in provider_data:
                self._deep_merge(provider_type_data, provider_data)
                continue

            vim_name = area_vim_info.get("vim_name")
            if not vim_name:
                vim_name = f"area_{area}"
                self.logger.warning(
                    f"Cannot find VIM name for area {area}, storing provider data under fallback VIM key {vim_name}"
                )

            vims_data = provider_type_data.setdefault("vims", {})
            vim_data = vims_data.setdefault(vim_name, {})

            if provider_type == EXTERNAL_REST_PROVIDER_TYPE:
                resource_groups = vim_data.setdefault("resource_groups", {})
                resource_group_data = resource_groups.setdefault(blueprint_id, {})
                self._deep_merge(resource_group_data, provider_data)
                continue

            if "resource_groups" in provider_data:
                self._deep_merge(vim_data, provider_data)
                continue

            resource_groups = vim_data.setdefault("resource_groups", {})
            resource_group_data = resource_groups.setdefault(blueprint_id, {})
            self._deep_merge(
                resource_group_data,
                self._clean_legacy_virtualization_resource_group_data(
                    provider_type,
                    provider_data,
                ),
            )

    def _migrate_kubernetes_data(
        self,
        legacy_doc: dict[str, Any],
        blueprint_id: str,
        provider_data_by_type: dict[str, dict],
        touched_provider_types: set[str],
    ) -> None:
        for area, legacy_provider in (legacy_doc.get("k8s") or {}).items():
            provider_data = self._extract_provider_data(legacy_provider)
            if not provider_data:
                continue

            target_data = provider_data_by_type.setdefault(KUBERNETES_PROVIDER_TYPE, {})
            touched_provider_types.add(KUBERNETES_PROVIDER_TYPE)

            if "areas" in provider_data:
                self._deep_merge(target_data, provider_data)
                continue

            areas_data = target_data.setdefault("areas", {})
            area_data = areas_data.setdefault(str(area), {})
            resource_groups = area_data.setdefault("resource_groups", {})
            resource_group_data = resource_groups.setdefault(blueprint_id, {})
            self._deep_merge(
                resource_group_data,
                {
                    "namespaces": provider_data.get("namespaces", []),
                    "reserved_ips": provider_data.get("reserved_ips", []),
                },
            )

    def _migrate_pdu_data(
        self,
        legacy_doc: dict[str, Any],
        blueprint_id: str,
        provider_data_by_type: dict[str, dict],
        touched_provider_types: set[str],
    ) -> None:
        provider_data = self._extract_provider_data(legacy_doc.get("pdu"))
        if not provider_data:
            return

        target_data = provider_data_by_type.setdefault(PDU_PROVIDER_TYPE, {})
        touched_provider_types.add(PDU_PROVIDER_TYPE)

        if "locked_pdus_by_blueprint" in provider_data:
            self._deep_merge(target_data, {
                "locked_pdus_by_blueprint": provider_data["locked_pdus_by_blueprint"],
            })

        if "locked_pdus" in provider_data:
            locked_pdus_by_blueprint = target_data.setdefault("locked_pdus_by_blueprint", {})
            locked_pdus = locked_pdus_by_blueprint.setdefault(blueprint_id, [])
            self._extend_unique(locked_pdus, provider_data["locked_pdus"])

    def _migrate_blueprint_data(
        self,
        legacy_doc: dict[str, Any],
        blueprint_id: str,
        provider_data_by_type: dict[str, dict],
        touched_provider_types: set[str],
    ) -> None:
        provider_data = self._extract_provider_data(legacy_doc.get("blueprint"))
        if not provider_data:
            return

        target_data = provider_data_by_type.setdefault(BLUEPRINT_PROVIDER_TYPE, {})
        touched_provider_types.add(BLUEPRINT_PROVIDER_TYPE)

        if "child_blueprints" in provider_data:
            self._deep_merge(target_data, {
                "child_blueprints": provider_data["child_blueprints"],
            })

        if "deployed_blueprints" in provider_data:
            child_blueprints = target_data.setdefault("child_blueprints", {})
            blueprint_children = child_blueprints.setdefault(blueprint_id, [])
            self._extend_unique(blueprint_children, provider_data["deployed_blueprints"])

    def _migrate_diagnostic_data(
        self,
        legacy_doc: dict[str, Any],
        blueprint_id: str,
        provider_data_by_type: dict[str, dict],
        touched_provider_types: set[str],
    ) -> None:
        provider_data = self._extract_provider_data(legacy_doc.get("diagnostic"))
        if not provider_data:
            return

        target_data = provider_data_by_type.setdefault(DIAGNOSTIC_PROVIDER_TYPE, {})
        touched_provider_types.add(DIAGNOSTIC_PROVIDER_TYPE)

        rpcapd_vm_deployments = target_data.setdefault("rpcapd_vm_deployments", [])
        deployments = deepcopy(provider_data.get("rpcapd_vm_deployments") or [])
        for deployment in deployments:
            vm_resource = deployment.get("vm_resource") if isinstance(deployment, dict) else None
            if isinstance(vm_resource, dict) and "resource_group" not in vm_resource:
                vm_resource["resource_group"] = blueprint_id
        self._extend_unique(rpcapd_vm_deployments, deployments)

    def _extract_provider_data(self, legacy_provider: dict[str, Any] | None) -> dict[str, Any]:
        if not legacy_provider or not isinstance(legacy_provider, dict):
            return {}
        if "provider_data" in legacy_provider:
            provider_data = legacy_provider.get("provider_data")
        else:
            provider_data = legacy_provider
        if not isinstance(provider_data, dict):
            return {}
        return deepcopy(provider_data)

    def _get_virtualization_provider_type(
        self,
        legacy_provider: dict[str, Any],
        fallback_vim_type: str | None,
    ) -> str | None:
        descriptor = (
            f"{legacy_provider.get('provider_type', '')} "
            f"{legacy_provider.get('provider_data_type', '')}"
        ).lower()

        if "openstack" in descriptor:
            return OPENSTACK_PROVIDER_TYPE
        if "proxmox" in descriptor:
            return PROXMOX_PROVIDER_TYPE
        if "external_rest" in descriptor or "virtualizationproviderrest" in descriptor:
            return EXTERNAL_REST_PROVIDER_TYPE
        return fallback_vim_type

    def _clean_legacy_virtualization_resource_group_data(
        self,
        provider_type: str,
        provider_data: dict[str, Any],
    ) -> dict[str, Any]:
        cleaned_provider_data = deepcopy(provider_data)
        if provider_type == PROXMOX_PROVIDER_TYPE:
            cleaned_provider_data.pop("proxmox_node_name", None)
            cleaned_provider_data.pop("proxmox_credentials", None)
            cleaned_provider_data.pop("storage_path", None)
        return cleaned_provider_data

    def _deep_merge(self, target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, source_value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(source_value, dict)
            ):
                self._deep_merge(target[key], source_value)
            elif (
                key in target
                and isinstance(target[key], list)
                and isinstance(source_value, list)
            ):
                self._extend_unique(target[key], source_value)
            else:
                target[key] = deepcopy(source_value)

    def _extend_unique(self, target: list[Any], source: list[Any]) -> None:
        for item in source:
            if item not in target:
                target.append(deepcopy(item))
