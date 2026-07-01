from types import SimpleNamespace
from typing import Any

from nfvcl_core_models.network.network_models import PduModel
from nfvcl_core_models.resources import (
    VmResource,
    VmResourceFlavor,
    VmResourceImage,
    VmResourceNetworkInterface,
    VmResourceNetworkInterfaceAddress,
)
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum


class SaveSpy:
    def __init__(self):
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class FakeTopology:
    def __init__(self, pdus: list[PduModel] | None = None):
        self._pdus = pdus or []

    def get_pdus(self) -> list[PduModel]:
        return self._pdus


class FakeTopologyManager:
    def __init__(self, pdus: list[PduModel] | None = None):
        self.topology = FakeTopology(pdus)
        self.updated_pdus: list[PduModel] = []
        self.created_pdus: list[PduModel] = []
        self.deleted_pdus: list[str] = []

    def get_topology(self) -> FakeTopology:
        return self.topology

    def update_pdu(self, pdu: PduModel) -> PduModel:
        self.updated_pdus.append(pdu)
        return pdu

    def create_pdu(self, pdu: PduModel) -> PduModel:
        self.created_pdus.append(pdu)
        self.topology.get_pdus().append(pdu)
        return pdu

    def delete_pdu(self, pdu_id: str) -> None:
        self.deleted_pdus.append(pdu_id)


class FakeVimClientPool:
    def __init__(self, client: Any):
        self.client = client
        self.clients = {client.vim.name: client}

    def get_client(self, area: int, expected_type: VimTypeEnum) -> Any:
        if self.client.vim.vim_type != expected_type:
            raise ValueError(f"Unexpected VIM type {self.client.vim.vim_type}")
        if area not in self.client.vim.areas:
            raise ValueError(f"Unexpected area {area}")
        return self.client

    def get_client_by_vim_name(self, vim_name: str, expected_type: VimTypeEnum) -> Any:
        if self.client.vim.vim_type != expected_type:
            raise ValueError(f"Unexpected VIM type {self.client.vim.vim_type}")
        if self.client.vim.name != vim_name:
            raise ValueError(f"Unexpected VIM {vim_name}")
        return self.client

    def get_vim(self, area: int, expected_type: VimTypeEnum) -> VimModel:
        return self.get_client(area, expected_type).vim

    def get_vim_by_name(self, vim_name: str, expected_type: VimTypeEnum) -> VimModel:
        return self.get_client_by_vim_name(vim_name, expected_type).vim

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()


def build_pdu(name: str = "pdu1", area: int = 1, instance_type: str = "test") -> PduModel:
    return PduModel.model_validate(
        {
            "name": name,
            "area": area,
            "type": "GNB",
            "instance_type": instance_type,
            "network_interfaces": [
                {
                    "name": "mgmt",
                    "mgmt": True,
                    "ip": "192.0.2.10",
                }
            ],
            "username": "user",
            "password": "password",
        }
    )


def build_vm_resource(created: bool = True, area: int = 1, resource_group: str = "rg") -> VmResource:
    vm = VmResource(
        id="vm-resource-id",
        resource_group=resource_group,
        area=area,
        name="vm1",
        image=VmResourceImage(name="ubuntu"),
        flavor=VmResourceFlavor(vcpu_count="1", memory_mb="1024", storage_gb="10"),
        username="ubuntu",
        password="ubuntu",
        management_network="mgmt",
        additional_networks=[],
        created=created,
        access_ip="192.0.2.20",
    )
    vm.network_interfaces["mgmt"] = [
        VmResourceNetworkInterface(
            fixed=VmResourceNetworkInterfaceAddress(
                interface_name="eth0",
                ip="192.0.2.20",
                mac="00:00:00:00:00:01",
                cidr="192.0.2.0/24",
            )
        )
    ]
    return vm


def build_vim(name: str, vim_type: VimTypeEnum = VimTypeEnum.OPENSTACK, area: int = 1) -> VimModel:
    return VimModel(
        name=name,
        vim_type=vim_type,
        vim_url="http://example.invalid",
        vim_user="user",
        vim_password="password",
        areas=[area],
        networks=["mgmt"],
    )


def namespace(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)
