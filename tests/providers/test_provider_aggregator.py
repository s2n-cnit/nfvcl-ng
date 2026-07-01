from nfvcl_core.blueprints.provider_aggregator import ProvidersAggregator


class FakeCleanupProvider:
    def __init__(self):
        self.cleaned_resource_groups: list[str] = []

    def cleanup_resource_group(self, resource_group: str):
        self.cleaned_resource_groups.append(resource_group)


class FakeProviderManager:
    def __init__(self):
        self.kubernetes_provider = FakeCleanupProvider()
        self.pdu_provider = FakeCleanupProvider()
        self.blueprint_provider = FakeCleanupProvider()
        self.diagnostic_provider = FakeCleanupProvider()

    def get_virtualization_providers(self):
        return []

    def get_kubernetes_provider(self, area: int | None = None):
        return self.kubernetes_provider

    def get_pdu_provider(self):
        return self.pdu_provider

    def get_blueprint_provider(self):
        return self.blueprint_provider

    def get_diagnostic_provider(self):
        return self.diagnostic_provider


def test_final_cleanup_calls_k8s_cleanup_without_prior_k8s_area_use():
    provider_manager = FakeProviderManager()
    aggregator = ProvidersAggregator(
        blueprint_id="blue-a",
        persistence_function=lambda: None,
        provider_manager=provider_manager,
        topology_manager=None,
        blueprint_manager=None,
    )

    aggregator.final_cleanup()

    assert provider_manager.kubernetes_provider.cleaned_resource_groups == ["blue-a"]
    assert provider_manager.pdu_provider.cleaned_resource_groups == ["blue-a"]
    assert provider_manager.blueprint_provider.cleaned_resource_groups == ["blue-a"]
    assert provider_manager.diagnostic_provider.cleaned_resource_groups == ["blue-a"]
