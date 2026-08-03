from __future__ import annotations

from typing import TYPE_CHECKING

from nfvcl_core.database.provider_repository import ProviderDataRepository
from nfvcl_core.managers.generic_manager import GenericManager
from nfvcl_core.managers.topology_manager import TopologyManager
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.vim.vim_models import VimModel, VimTypeEnum

from nfvcl_providers.provider_interface import ProviderInterface
from nfvcl_providers.virtualization import vim_type_to_provider_mapping
from nfvcl_providers.virtualization.virtualization_provider_interface import VirtualizationProviderInterface
from nfvcl_providers.vim_clients.vim_context import VimClientPool

if TYPE_CHECKING:
    from nfvcl_core.managers.blueprint_manager import BlueprintManager
    from nfvcl_core.managers.pdu_manager import PDUManager
    from nfvcl_providers.blueprint.blueprint_provider import BlueprintProvider
    from nfvcl_providers.diagnostic.diagnostic_provider import DiagnosticProvider
    from nfvcl_providers.kubernetes.k8s_provider_interface import K8SProviderInterface
    from nfvcl_providers.pdu.pdu_provider import PDUProvider

BLUEPRINT_PROVIDER_TYPE = "blueprint"
DIAGNOSTIC_PROVIDER_TYPE = "diagnostic"
KUBERNETES_PROVIDER_TYPE = "kubernetes"
PDU_PROVIDER_TYPE = "pdu"


class TopologyVimModelResolver:
    def __init__(self, topology_manager: TopologyManager):
        self._topology_manager = topology_manager

    def get_vim_by_area(self, area: int) -> VimModel:
        return self._topology_manager.get_topology().get_vim_by_area(area)

    def get_vim_by_name(self, vim_name: str) -> VimModel:
        return self._topology_manager.get_topology().get_vim(vim_name)


class ProviderManager(GenericManager):
    """
    This class is used to load and store references to all the providers
    It also handles the database data save and load
    """

    def __init__(
        self,
        provider_data_repository: ProviderDataRepository,
        topology_manager: TopologyManager,
        blueprint_manager: BlueprintManager | None = None,
        pdu_manager: PDUManager | None = None,
    ):
        super().__init__()
        self._provider_data_repository = provider_data_repository
        self._topology_manager = topology_manager
        self._blueprint_manager = blueprint_manager
        self._pdu_manager = pdu_manager
        self._vim_client_pool = VimClientPool(TopologyVimModelResolver(topology_manager))
        self._virtualization_providers: dict[VimTypeEnum, VirtualizationProviderInterface] = {}
        self._blueprint_provider: BlueprintProvider | None = None
        self._diagnostic_provider: DiagnosticProvider | None = None
        self._kubernetes_provider: K8SProviderInterface | None = None
        self._pdu_provider: PDUProvider | None = None
        self.load()

    def load(self):
        for vim_type in vim_type_to_provider_mapping:
            self.get_virtualization_provider(vim_type)
        if self._blueprint_manager is not None:
            self.get_blueprint_provider()
        self.get_diagnostic_provider()
        if self._pdu_manager is not None:
            self.get_pdu_provider()

    def get_virtualization_provider(self, vim_type: VimTypeEnum | str) -> VirtualizationProviderInterface:
        """
        Get virtualization provider for given vim type. Area is not needed because it is managed by the provider itself.

        Args:
            vim_type: Vim type for which the provider is requested.

        Returns:
            Virtualization provider for given vim type.
        """
        vim_type = self._normalize_vim_type(vim_type)
        if vim_type not in self._virtualization_providers:
            provider_class = vim_type_to_provider_mapping[vim_type]
            provider = provider_class(
                vim_client_pool=self._vim_client_pool,
                persistence_function=lambda vim_type=vim_type: self.save_virtualization_provider_data(vim_type)
            )

            self._load_provider_data(self._get_provider_type_key(vim_type), provider)

            self._virtualization_providers[vim_type] = provider
        return self._virtualization_providers[vim_type]

    def get_blueprint_provider(self) -> BlueprintProvider:
        if self._blueprint_manager is None:
            raise ValueError("BlueprintProvider requires a BlueprintManager")
        if self._blueprint_provider is None:
            from nfvcl_providers.blueprint.blueprint_provider import BlueprintProvider

            provider = BlueprintProvider(
                blueprint_manager=self._blueprint_manager,
                persistence_function=self.save_blueprint_provider_data,
            )
            self._load_provider_data(BLUEPRINT_PROVIDER_TYPE, provider)
            self._blueprint_provider = provider
        return self._blueprint_provider

    def get_diagnostic_provider(self) -> DiagnosticProvider:
        if self._diagnostic_provider is None:
            from nfvcl_providers.diagnostic.diagnostic_provider import DiagnosticProvider

            provider = DiagnosticProvider(
                persistence_function=self.save_diagnostic_provider_data,
            )
            self._load_provider_data(DIAGNOSTIC_PROVIDER_TYPE, provider)
            self._diagnostic_provider = provider
        return self._diagnostic_provider

    def get_kubernetes_provider(self, area: int | None = None) -> K8SProviderInterface:
        if self._kubernetes_provider is None:
            from nfvcl_providers.kubernetes.k8s_provider_native import K8SProviderNative

            provider = K8SProviderNative(
                topology_manager=self._topology_manager,
                persistence_function=self.save_kubernetes_provider_data,
            )
            self._load_provider_data(KUBERNETES_PROVIDER_TYPE, provider)
            self._kubernetes_provider = provider
        return self._kubernetes_provider

    def set_blueprint_manager(self, blueprint_manager: BlueprintManager):
        if self._blueprint_manager is blueprint_manager:
            return
        self._blueprint_manager = blueprint_manager
        self._blueprint_provider = None
        self.get_blueprint_provider()

    def get_virtualization_provider_for_area(self, area: int) -> VirtualizationProviderInterface:
        """
        Returns the virtualization provider for the given area.

        Args:
            area: The area for which to retrieve the virtualization provider.

        Returns:
            The virtualization provider for the given area.
        """
        vim = self._topology_manager.get_topology().get_vim_by_area(area) # Throws Exception
        return self.get_virtualization_provider(vim.vim_type)

    def get_virtualization_providers(self) -> list[VirtualizationProviderInterface]:
        return list(self._virtualization_providers.values())

    def get_pdu_provider(self) -> PDUProvider:
        if self._pdu_manager is None:
            raise ValueError("PDUProvider requires a PDUManager")
        if self._pdu_provider is None:
            from nfvcl_providers.pdu.pdu_provider import PDUProvider

            provider = PDUProvider(
                topology_manager=self._topology_manager,
                pdu_manager=self._pdu_manager,
                persistence_function=self.save_pdu_provider_data,
            )
            self._load_provider_data(PDU_PROVIDER_TYPE, provider)
            self._pdu_provider = provider
        return self._pdu_provider

    def get_virtualization_provider_data(self, vim_type: VimTypeEnum | str) -> ProviderData:
        return self.get_virtualization_provider(vim_type).data

    def get_blueprint_provider_data(self) -> ProviderData:
        return self.get_blueprint_provider().data

    def get_diagnostic_provider_data(self) -> ProviderData:
        return self.get_diagnostic_provider().data

    def get_kubernetes_provider_data(self, area: int | None = None) -> ProviderData:
        return self.get_kubernetes_provider(area).data

    def get_pdu_provider_data(self) -> ProviderData:
        return self.get_pdu_provider().data

    def save_virtualization_provider_data(self, vim_type: VimTypeEnum | str):
        vim_type = self._normalize_vim_type(vim_type)
        provider = self.get_virtualization_provider(vim_type)
        self._save_provider_data(self._get_provider_type_key(vim_type), provider)

    def save_blueprint_provider_data(self):
        self._save_provider_data(BLUEPRINT_PROVIDER_TYPE, self.get_blueprint_provider())

    def save_diagnostic_provider_data(self):
        self._save_provider_data(DIAGNOSTIC_PROVIDER_TYPE, self.get_diagnostic_provider())

    def save_kubernetes_provider_data(self):
        if self._kubernetes_provider is not None:
            self._save_provider_data(KUBERNETES_PROVIDER_TYPE, self._kubernetes_provider)

    def save_pdu_provider_data(self):
        self._save_provider_data(PDU_PROVIDER_TYPE, self.get_pdu_provider())

    def save_all(self):
        for vim_type in self._virtualization_providers:
            self.save_virtualization_provider_data(vim_type)
        if self._blueprint_provider is not None:
            self.save_blueprint_provider_data()
        if self._diagnostic_provider is not None:
            self.save_diagnostic_provider_data()
        if self._kubernetes_provider is not None:
            self.save_kubernetes_provider_data()
        if self._pdu_provider is not None:
            self.save_pdu_provider_data()

    def _normalize_vim_type(self, vim_type: VimTypeEnum | str) -> VimTypeEnum:
        if isinstance(vim_type, VimTypeEnum):
            return vim_type
        return VimTypeEnum(vim_type)

    def _get_provider_type_key(self, vim_type: VimTypeEnum) -> str:
        return vim_type.value

    def _load_provider_data(
        self,
        provider_type: str,
        provider: ProviderInterface,
    ):
        saved_data = self._provider_data_repository.find_by_provider_type(
            provider_type,
            type(provider.data),
        )
        if saved_data is not None:
            provider.data = saved_data

    def _save_provider_data(
        self,
        provider_type: str,
        provider: ProviderInterface,
    ):
        self._provider_data_repository.save_provider_type_data(
            provider_type,
            provider.data,
        )
