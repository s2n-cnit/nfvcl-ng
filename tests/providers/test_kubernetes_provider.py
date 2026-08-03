from nfvcl_core_models.network.network_models import MultusInterface
from nfvcl_core_models.topology_k8s_model import TopologyK8sModel
from nfvcl_providers.kubernetes.k8s_provider_native import K8SProviderNative
from tests.providers.fakes import SaveSpy


class FakeKubeUtils:
    def __init__(self):
        self.deleted_namespaces: list[str] = []

    def delete_namespace(self, namespace: str) -> None:
        self.deleted_namespaces.append(namespace)


class FakeK8sTopologyManager:
    def __init__(self):
        self.cluster = TopologyK8sModel(
            name="k8s-a",
            provided_by="EXTERNAL",
            credentials="",
            areas=[1],
            networks=[],
        )
        self.reserved: list[tuple[str, str]] = []
        self.released: list[tuple[str, str, object]] = []

    def get_k8s_cluster_by_area(self, area: int) -> TopologyK8sModel:
        assert area == 1
        return self.cluster

    def reserve_k8s_multus_ip(self, cluster_name: str, network_name: str) -> MultusInterface:
        self.reserved.append((cluster_name, network_name))
        return MultusInterface(
            ip_address="10.0.0.10",
            gateway_ip="10.0.0.1",
            network_cidr="10.0.0.0/24",
            host_interface="eth1",
            prefixlen=24,
            network_name=network_name,
        )

    def release_k8s_multus_ip(self, cluster_name: str, network_name: str, ip_address):
        self.released.append((cluster_name, network_name, ip_address))
        return MultusInterface(
            ip_address=ip_address,
            gateway_ip="10.0.0.1",
            network_cidr="10.0.0.0/24",
            host_interface="eth1",
            prefixlen=24,
            network_name=network_name,
        )


def test_k8s_provider_tracks_reserved_multus_ips():
    topology_manager = FakeK8sTopologyManager()
    provider = K8SProviderNative(topology_manager=topology_manager)

    reserved = provider.reserve_k8s_multus_ip(1, "rg", "n3")

    assert reserved.network_name == "n3"
    assert provider.data.get_area_data(1).get_resource_group_data("rg").reserved_ips == [reserved]
    assert topology_manager.reserved == [("k8s-a", "n3")]

    released = provider.release_k8s_multus_ip(1, "rg", "n3", reserved.ip_address)

    assert released.ip_address == reserved.ip_address
    assert provider.data.get_area_data(1).get_resource_group_data("rg").reserved_ips == []
    assert topology_manager.released == [("k8s-a", "n3", reserved.ip_address)]


def test_k8s_provider_cleanup_deletes_namespaces_and_releases_ips(monkeypatch):
    topology_manager = FakeK8sTopologyManager()
    save = SaveSpy()
    provider = K8SProviderNative(topology_manager=topology_manager, persistence_function=save)
    kube_utils = FakeKubeUtils()
    monkeypatch.setattr(provider, "get_kube_utils_by_area", lambda area: kube_utils)

    reserved = provider.reserve_k8s_multus_ip(1, "rg", "n3")
    provider.data.get_area_data(1).get_resource_group_data("rg").namespaces.append("test-ns")

    provider.cleanup_resource_group("rg")

    assert kube_utils.deleted_namespaces == ["test-ns"]
    assert topology_manager.released == [("k8s-a", "n3", reserved.ip_address)]
