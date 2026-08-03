from enum import Enum
from typing import Callable, Optional

from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_core_models.providers.diagnostic import (
    DiagnosticProviderData,
    DiagnosticProviderException,
    RpcapdVmDeployment,
    RpcapdVmStatus,
)
from nfvcl_core_models.resources import VmResource, VmResourceAnsibleConfiguration
from nfvcl_providers.provider_interface import ProviderInterface
from nfvcl_providers.virtualization.common.utils import configure_vm_ansible

RPCAPD_DOWNLOAD_URL = "https://example.invalid/nfvcl/diagnostic/rpcapd"
RPCAPD_BINARY_PATH = "/usr/local/bin/rpcapd"
RPCAPD_SERVICE_NAME = "rpcapd"
RPCAPD_SERVICE_PATH = f"/etc/systemd/system/{RPCAPD_SERVICE_NAME}.service"


class RpcapdVmOperation(str, Enum):
    INSTALL = "install"
    UNINSTALL = "uninstall"
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"


class RpcapdVmConfigurator(VmResourceAnsibleConfiguration):
    operation: RpcapdVmOperation = Field()
    download_url: str = Field(default=RPCAPD_DOWNLOAD_URL)

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder(
            f"rpcapd {self.operation} on {self.vm_resource.name}"
        )

        if self.operation == RpcapdVmOperation.INSTALL:
            self._add_install_tasks(ansible_builder)
        elif self.operation == RpcapdVmOperation.UNINSTALL:
            self._add_uninstall_tasks(ansible_builder)
        elif self.operation == RpcapdVmOperation.START:
            ansible_builder.add_service_task(
                RPCAPD_SERVICE_NAME, ServiceState.STARTED
            )
        elif self.operation == RpcapdVmOperation.STOP:
            ansible_builder.add_service_task(
                RPCAPD_SERVICE_NAME, ServiceState.STOPPED
            )
        elif self.operation == RpcapdVmOperation.RESTART:
            ansible_builder.add_service_task(
                RPCAPD_SERVICE_NAME, ServiceState.RESTARTED
            )
        elif self.operation == RpcapdVmOperation.STATUS:
            self._add_status_tasks(ansible_builder)

        return ansible_builder.build()

    def _add_install_tasks(self, ansible_builder: AnsiblePlaybookBuilder) -> None:
        ansible_builder.add_task(
            "Download rpcapd",
            "ansible.builtin.get_url",
            {
                "url": self.download_url,
                "dest": RPCAPD_BINARY_PATH,
                "mode": "0755",
                "force": True,
            },
        )
        ansible_builder.add_copy_content_task(
            content=(
                "[Unit]\n"
                "Description=Remote packet capture daemon\n"
                "After=network-online.target\n"
                "Wants=network-online.target\n"
                "\n"
                "[Service]\n"
                "Type=simple\n"
                f"ExecStart={RPCAPD_BINARY_PATH} -4 -n\n"
                "Restart=on-failure\n"
                "RestartSec=2\n"
                "\n"
                "[Install]\n"
                "WantedBy=multi-user.target\n"
            ),
            dest=RPCAPD_SERVICE_PATH,
            mode=0o644,
        )
        ansible_builder.add_task(
            "Reload systemd after installing rpcapd",
            "ansible.builtin.systemd_service",
            {"daemon_reload": True},
        )
        ansible_builder.add_service_task(
            RPCAPD_SERVICE_NAME, ServiceState.STARTED
        )

    def _add_uninstall_tasks(self, ansible_builder: AnsiblePlaybookBuilder) -> None:
        ansible_builder.add_shell_task(
            f"systemctl disable --now {RPCAPD_SERVICE_NAME} 2>/dev/null || true"
        )
        ansible_builder.add_task(
            "Remove rpcapd service",
            "ansible.builtin.file",
            {"path": RPCAPD_SERVICE_PATH, "state": "absent"},
        )
        ansible_builder.add_task(
            "Remove rpcapd binary",
            "ansible.builtin.file",
            {"path": RPCAPD_BINARY_PATH, "state": "absent"},
        )
        ansible_builder.add_task(
            "Reload systemd after uninstalling rpcapd",
            "ansible.builtin.systemd_service",
            {"daemon_reload": True},
        )

    def _add_status_tasks(self, ansible_builder: AnsiblePlaybookBuilder) -> None:
        ansible_builder.add_run_command_and_gather_output_tasks(
            f"test -x {RPCAPD_BINARY_PATH} && echo true || echo false",
            "rpcapd_installed",
        )
        ansible_builder.add_run_command_and_gather_output_tasks(
            f"systemctl is-active {RPCAPD_SERVICE_NAME} 2>/dev/null || true",
            "rpcapd_service_state",
        )


class DiagnosticProvider(ProviderInterface):
    data: DiagnosticProviderData

    def __init__(
        self,
        persistence_function: Optional[Callable[[], None]] = None,
    ):
        super().__init__(persistence_function)

    def init(self) -> None:
        self.data: DiagnosticProviderData = DiagnosticProviderData()

    def install_rpcapd(
        self,
        vm_resource: VmResource,
        download_url: str = RPCAPD_DOWNLOAD_URL,
    ) -> RpcapdVmStatus:
        self._run_rpcapd_operation(
            vm_resource,
            RpcapdVmOperation.INSTALL,
            download_url=download_url,
        )

        deployment = self._find_rpcapd_deployment(vm_resource)
        if deployment:
            deployment.vm_resource = vm_resource
        else:
            self.data.rpcapd_vm_deployments.append(
                RpcapdVmDeployment(vm_resource=vm_resource)
            )
        self._save_provider_data()
        return self.get_rpcapd_status(vm_resource)

    def uninstall_rpcapd(self, vm_resource: VmResource) -> None:
        self._run_rpcapd_operation(
            vm_resource,
            RpcapdVmOperation.UNINSTALL,
        )
        deployment = self._find_rpcapd_deployment(vm_resource)
        if deployment:
            self.data.rpcapd_vm_deployments.remove(deployment)
            self._save_provider_data()

    def start_rpcapd(self, vm_resource: VmResource) -> RpcapdVmStatus:
        self._ensure_rpcapd_managed(vm_resource)
        self._run_rpcapd_operation(vm_resource, RpcapdVmOperation.START)
        return self.get_rpcapd_status(vm_resource)

    def stop_rpcapd(self, vm_resource: VmResource) -> RpcapdVmStatus:
        self._ensure_rpcapd_managed(vm_resource)
        self._run_rpcapd_operation(vm_resource, RpcapdVmOperation.STOP)
        return self.get_rpcapd_status(vm_resource)

    def restart_rpcapd(self, vm_resource: VmResource) -> RpcapdVmStatus:
        self._ensure_rpcapd_managed(vm_resource)
        self._run_rpcapd_operation(vm_resource, RpcapdVmOperation.RESTART)
        return self.get_rpcapd_status(vm_resource)

    def get_rpcapd_status(self, vm_resource: VmResource) -> RpcapdVmStatus:
        facts = self._run_rpcapd_operation(
            vm_resource,
            RpcapdVmOperation.STATUS,
        )
        service_state = (
            str(facts.get("rpcapd_service_state", "unknown")).strip() or "unknown"
        )
        installed = str(facts.get("rpcapd_installed", "false")).strip() == "true"

        return RpcapdVmStatus(
            vm_name=vm_resource.name,
            installed=installed,
            running=service_state == "active",
            service_state=service_state,
        )

    def _run_rpcapd_operation(
        self,
        vm_resource: VmResource,
        operation: RpcapdVmOperation,
        download_url: str = RPCAPD_DOWNLOAD_URL,
    ) -> dict:
        self.logger.info(
            f"Running rpcapd operation '{operation}' on VM '{vm_resource.name}'"
        )
        return configure_vm_ansible(
            RpcapdVmConfigurator(
                vm_resource=vm_resource,
                operation=operation,
                download_url=download_url,
                resource_group=vm_resource.resource_group,
            ),
            vm_resource.resource_group,
            logger_override=self.logger,
        )

    def _find_rpcapd_deployment(
        self,
        vm_resource: VmResource,
    ) -> Optional[RpcapdVmDeployment]:
        for deployment in self.data.rpcapd_vm_deployments:
            if (
                deployment.vm_resource.resource_group == vm_resource.resource_group
                and deployment.vm_resource.area == vm_resource.area
                and deployment.vm_resource.name == vm_resource.name
            ):
                return deployment
        return None

    def _ensure_rpcapd_managed(self, vm_resource: VmResource) -> None:
        if not self._find_rpcapd_deployment(vm_resource):
            raise DiagnosticProviderException(
                f"rpcapd is not managed on VM '{vm_resource.name}'"
            )

    def _save_provider_data(self) -> None:
        if self.save_to_db:
            self.save_to_db()

    def cleanup_resource_group(self, resource_group: str) -> None:
        for deployment in list(self.data.rpcapd_vm_deployments):
            if deployment.vm_resource.resource_group != resource_group:
                continue
            self.logger.warning(
                f"Uninstalling leftover rpcapd deployment from VM "
                f"'{deployment.vm_resource.name}'"
            )
            try:
                self.uninstall_rpcapd(deployment.vm_resource)
            except Exception as exc:
                self.logger.error(
                    f"Cannot uninstall rpcapd from VM "
                    f"'{deployment.vm_resource.name}': {exc}"
                )
        self._save_provider_data()
