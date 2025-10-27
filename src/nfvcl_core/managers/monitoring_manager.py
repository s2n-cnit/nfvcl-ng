from typing import Dict

from grafana_client import GrafanaApi
from grafana_client.client import GrafanaClientError

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_core.managers import TopologyManager
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_common.ansible_utils import run_ansible_playbook
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.monitoring.grafana_model import GrafanaFolderModel, GrafanaDashboardModel


class MonitoringManager(GenericManager):
    def __init__(self, topology_manager: TopologyManager):
        super().__init__()
        self._topology_manager = topology_manager

    def sync_prometheus_targets_to_server(self, prometheus_server_id: str):
        prometheus_server = self._topology_manager.get_prometheus(prometheus_server_id)
        if not prometheus_server:
            raise NFVCLCoreException(f"Prometheus server with ID '{prometheus_server_id}' not found in topology")

        playbook_builder = AnsiblePlaybookBuilder(
            name=f"Upload Prometheus targets file to {prometheus_server_id}",
        )

        playbook_builder.add_copy_task(prometheus_server.dump_sd_file(), prometheus_server.sd_file_location)

        # Execute the playbook
        try:
            result, fact_cache = run_ansible_playbook(
                host=prometheus_server.ip,
                username=prometheus_server.user,
                password=prometheus_server.password,
                playbook=playbook_builder.build(),
                logger=self.logger
            )

            if result.status == "successful":
                self.logger.info(f"Successfully uploaded Prometheus targets file to {prometheus_server.ip}")
            else:
                self.logger.error(f"Failed to upload Prometheus targets file. Status: {result.status}")

            return result, fact_cache

        except Exception as e:
            self.logger.error(f"Error executing Ansible playbook: {str(e)}")
            raise

    def sync_grafana_folders_to_server(self, grafana_server_id: str):
        grafana_server = self._topology_manager.get_grafana(grafana_server_id)
        if not grafana_server:
            raise NFVCLCoreException(f"Grafana server with ID '{grafana_server_id}' not found in topology")

        grafana_client = GrafanaApi.from_url(
            url=f"http://{grafana_server.ip}:{grafana_server.port}",
            credential=(grafana_server.user, grafana_server.password),
        )

        # Create folders recursively
        def rec(folder_model: GrafanaFolderModel, parent_uid=None):
            if folder_model.uid is None:
                self.logger.info(f"Creating Grafana folder '{folder_model.name}' with parent UID: {parent_uid}")
                created_folder = grafana_client.folder.create_folder(folder_model.name, parent_uid=parent_uid)
                folder_model.uid = created_folder.get("uid")

            for subfolder in folder_model.folders:
                rec(subfolder, parent_uid=folder_model.uid)

        rec(grafana_server.root_folder, None)

        # Delete folders that are not in the topology
        folders_on_grafana = grafana_client.folder.get_all_folders(grafana_server.root_folder.uid)
        folders_in_topology = grafana_server.folder_tree()

        for folder in folders_on_grafana:
            if folder["uid"] not in folders_in_topology:
                self.logger.debug(f"Folder with UID {folder['uid']} exists on Grafana but not in topology. Removing it.")
                grafana_client.folder.delete_folder(folder["uid"])

        self._topology_manager.save_to_db()

    def get_grafana_datasource_uid(self, grafana_server_id: str, datasource_name: str) -> str:
        grafana_server = self._topology_manager.get_grafana(grafana_server_id)
        if not grafana_server:
            raise NFVCLCoreException(f"Grafana server with ID '{grafana_server_id}' not found in topology")

        grafana_client = GrafanaApi.from_url(
            url=f"http://{grafana_server.ip}:{grafana_server.port}",
            credential=(grafana_server.user, grafana_server.password),
        )

        datasource = grafana_client.datasource.get_datasource_by_name(datasource_name)
        if datasource is None:
            raise NFVCLCoreException(f"Datasource '{datasource_name}' not found in Grafana server '{grafana_server_id}'")

        return datasource["uid"]

    def add_grafana_datasource(self, grafana_server_id: str, datasource: Dict[str, str]):
        grafana_server = self._topology_manager.get_grafana(grafana_server_id)
        if not grafana_server:
            raise NFVCLCoreException(f"Grafana server with ID '{grafana_server_id}' not found in topology")

        grafana_client = GrafanaApi.from_url(
            url=f"http://{grafana_server.ip}:{grafana_server.port}",
            credential=(grafana_server.user, grafana_server.password),
        )
        try:
            grafana_client.datasource.get_datasource_by_name(datasource["name"])
            existing_datasource = True
        except GrafanaClientError:
            existing_datasource = False

        if existing_datasource:
            self.logger.warning(f"Datasource '{datasource["name"]}' already exists in Grafana server '{grafana_server_id}'. Skipping creation.")
            return

        result = grafana_client.datasource.create_datasource(datasource)
        if "id" in result:
            self.logger.success(f"Datasource of type {datasource["type"]} added to Grafana server '{grafana_server_id}'")
        else:
            self.logger.error(f"Failed to add datasource: {result}")
            raise NFVCLCoreException(f"Failed to add datasource: {result}")

    def add_grafana_prometheus(self, grafana_server_id: str, prometheus_server_id: str):
        prometheus_server = self._topology_manager.get_prometheus(prometheus_server_id)
        if not prometheus_server:
            raise NFVCLCoreException(f"Prometheus server with ID '{prometheus_server_id}' not found in topology")

        datasource = {
            "name": prometheus_server.id,
            "type": "prometheus",
            "access": "proxy",
            "url": f"http://{prometheus_server.ip}:{prometheus_server.port}",
        }

        self.add_grafana_datasource(grafana_server_id, datasource)

    def add_grafana_loki(self, grafana_server_id: str):
        grafana_server = self._topology_manager.get_grafana(grafana_server_id)
        if not grafana_server:
            raise NFVCLCoreException(f"Grafana server with ID '{grafana_server_id}' not found in topology")

        datasource = {
            "name": "Loki",
            "type": "loki",
            "access": "proxy",
            "url": f"http://{grafana_server.ip}:3100",
            "basicAuth": False,
            "isDefault": False,
            "jsonData": {
                "httpMethod": "GET"
            }
        }
        self.add_grafana_datasource(grafana_server_id, datasource)

    def add_grafana_dashboard(self, grafana_server_id: str, dashboard: Dict, folder_uid: str = "0"):
        grafana_server = self._topology_manager.get_grafana(grafana_server_id)
        if not grafana_server:
            raise NFVCLCoreException(f"Grafana server with ID '{grafana_server_id}' not found in topology")

        grafana_client = GrafanaApi.from_url(
            url=f"http://{grafana_server.ip}:{grafana_server.port}",
            credential=(grafana_server.user, grafana_server.password),
        )

        try:
            payload = {
                "dashboard": dashboard,
                "folderUid": folder_uid,
                "overwrite": True
            }
            result = grafana_client.dashboard.update_dashboard(payload)

            if result.get("status") == "success":
                self.logger.info(f"Dashboard '{dashboard["title"]}' imported into folder with uid '{folder_uid}'")
                grafana_server.root_folder.find_folder_by_uid(folder_uid).dashboards.append(
                    GrafanaDashboardModel(uid=result["uid"], name=dashboard["title"])
                )
                self._topology_manager.save_to_db()
            else:
                self.logger.error("Failed to import dashboard:", result)

        except Exception as e:
            self.logger.error(f"Error adding/updating Grafana dashboard: {str(e)}")
            raise NFVCLCoreException(f"Failed to add/update Grafana dashboard: {str(e)}")
