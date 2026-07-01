import copy
from typing import Optional

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g_upf import DeployedUPFInfo
from nfvcl.blueprints_ng.modules.router_5g.router_5g import Router5GCreateModel, Router5GCreateModelNetworks
from nfvcl_core_models.custom_types import NFVCLCoreException
from pydantic import Field

from nfvcl.blueprints_ng.modules.amarisoft_core.amari_configurators import AmarisoftInstallator, AmarisoftConfigurator, AmarisoftSubscriberConfigurator
from nfvcl_core_models.network.ipam_models import SerializableIPv4Network, SerializableIPv4Address
from nfvcl_core_models.resources import VmResource, VmResourceImage, VmResourceFlavor

from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNG, Generic5GBlueprintNGState, UPFInfo, EdgeAreaInfo
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubSliceProfiles, SubSubscribers, SubArea, SubDataNets, Router5GNetworkInfo
from nfvcl_models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, Core5GDelSliceModel, Core5GAddSliceModel, Core5GAddDnnModel, Core5GDelDnnModel, Core5GAddTacModel, Core5GDelTacModel
from nfvcl_models.blueprint_ng.g5.upf import UPFNetworkInfo, Slice5GWithDNNs, BlueCreateModelNetworks, UPFBlueCreateModel

BASE_IMAGE24 = "ubuntu-lab-v0.1.6"
BASE_IMAGE24_URL = "https://images.tnt-lab.unige.it/ubuntu-lab/ubuntu-lab-v0.1.6-ubuntu2404.qcow2"
AMARISOFT_BLUE_TYPE = "amarisoft"
DEFAULT_FLAVOR = VmResourceFlavor(memory_mb="4096", storage_gb='32', vcpu_count='6')
ROUTER_BLUEPRINT_TYPE = "router_5g"
ROUTER_GET_INFO_FUNCTION = "get_router_info"

# Amarisoft handles user-plane forwarding internally (integrated UPF/NAT).
# There is no separate N6 interface on the core VM, so these placeholders
# are used to satisfy the required fields of UPFNetworkInfo without carrying
# real network data.
_N6_PLACEHOLDER_CIDR = "128.0.0.0/24"
_N6_PLACEHOLDER_IP = "128.0.0.1"


class AmarisoftCoreBlueprintNGState(Generic5GBlueprintNGState):
    """
    Persisted state for the Amarisoft 5G Core blueprint.

    All fields are Optional because the state object is constructed empty at
    load time and populated incrementally during the create workflow.
    """
    core_vm: Optional[VmResource] = Field(
        default=None,
        description="Virtual machine hosting the Amarisoft 5G core"
    )
    core_vm_networks_mapping: Optional[BlueCreateModelNetworks] = Field(
        default=None,
        description="Network interface mapping for the core VM (mgt / n3 / n4 / n6 / gnb)"
    )
    core_vm_installer: Optional[AmarisoftInstallator] = Field(
        default=None,
        description="Ansible configurator that installs the Amarisoft software on the core VM"
    )
    core_vm_configurator: Optional[AmarisoftConfigurator] = Field(
        default=None,
        description="Ansible configurator that applies the running configuration to the core VM"
    )
    core_vm_subscriber_configurator: Optional[AmarisoftSubscriberConfigurator] = Field(
        default=None,
        description="Ansible configurator that updates only the UE database on the core VM"
    )
    upf_info: Optional[UPFInfo] = Field(
        default=None,
        description=(
            "UPF information derived from the core VM itself (Amarisoft integrates the UPF). "
            "Stored so that edge-area registration and day-2 DNN operations can reuse it "
            "without re-querying the provider."
        )
    )


@blueprint_type(AMARISOFT_BLUE_TYPE)
class AmarisoftCore(Generic5GBlueprintNG[AmarisoftCoreBlueprintNGState, Create5gModel]):
    """
    Blueprint for an Amarisoft 5G Core deployment.

    Amarisoft runs as a combined MME/AMF + integrated UPF on a single VM.
    A Router5G child blueprint is deployed alongside the core to handle
    gNB-facing and N6 routing; the Amarisoft MME connects to it via its
    N3 interface.

    Day-2 operations (add/del subscriber, slice, DNN) are applied by
    re-running the AmarisoftConfigurator Ansible playbook, which regenerates
    and pushes all configuration files without restarting the service.
    """

    def __init__(self, blueprint_id: str, state_type: type[Generic5GBlueprintNGState] = AmarisoftCoreBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def create(self, create_model: Create5gModel):
        """
        We override the function to avoid calling self.update_edge_areas() before the core exists.

        Full day-0 creation workflow:

        1. Validate and store the requested configuration.
        2. Allocate network resources (``prepare_network``).
        3. Deploy and configure the core VM (``create_5g``).
        4. Register edge-area / UPF information with the parent class.
        5. Notify attached gNBs of the new core.
        """
        self.state.current_config = copy.deepcopy(create_model)
        self.configuration_feasibility_check(create_model)
        self.pre_creation_checks()

        self.prepare_network()
        self.create_5g(create_model)
        self.wait_core_ready()
        # Register edge-area UPF info that was built during create_5g
        self.update_edge_areas()
        self.update_gnb_configs()

        self.post_creation()
        self.logger.success("5G Blueprint completely deployed")

    def create_5g(self, create_model: Create5gModel):
        """
        Orchestrates the Amarisoft-specific deployment steps in order:

        1. Pre-condition checks (single area, licence server present).
        2. Build the VM network mapping from the create model.
        3. Spin up the core VM and install Amarisoft.
        4. Deploy the companion Router5G blueprint and retrieve its network info.
        5. Build UPF info (the core VM acts as the UPF).
        6. Apply the initial Amarisoft configuration via Ansible.
        """
        self._validate_create_preconditions()

        vm_networks = self._build_network_mapping()
        virtual_machine = self._create_core_vm(vm_networks)
        self._install_amarisoft(virtual_machine)

        # We only have 1 area, so we can safely take the first one without searching by ID
        area_id = self.state.current_config.areas[0].id
        served_slices = [
            Slice5GWithDNNs.from_slice_profile(sp, self.state.current_config.config.network_endpoints.data_nets)
            for sp in self.state.current_config.config.sliceProfiles
        ]

        router_info = self._deploy_router(area_id, vm_networks)
        self._build_upf_info(area_id, served_slices, vm_networks, router_info)
        self._configure_core(virtual_machine, vm_networks, router_info)

    def destroy(self):
        """Delegates full teardown to the parent class."""
        super().destroy()

    # -------------------------------------------------------------------------
    # create_5g helpers
    # -------------------------------------------------------------------------

    def _validate_create_preconditions(self):
        """
        Validates the constraints specific to Amarisoft before deployment begins.

        Raises:
            NFVCLCoreException: if more than one area is requested (not yet supported)
                                or the licence server address is missing.
        """
        if len(self.state.current_config.areas) > 1:
            raise NFVCLCoreException("Amarisoft does not support multiple areas yet")
        if self.state.current_config.config.licence_server is None:
            raise NFVCLCoreException("Licence server is not defined")

    def _build_network_mapping(self) -> BlueCreateModelNetworks:
        """
        Assembles the core VM network mapping from the create model and saves
        it to state for later reference (e.g. ``get_amf_ip``).

        The mapping collects:
        - ``mgt`` / ``n4``: from the global network endpoints (shared across all areas).
        - ``n3`` / ``n6`` / ``gnb``: from the single configured area.

        Returns:
            The populated BlueCreateModelNetworks instance.
        """
        vm_networks = BlueCreateModelNetworks(
            mgt=self.state.current_config.config.network_endpoints.mgt,
            n4=self.state.current_config.config.network_endpoints.n4,  # 5GC control plane (AMF, SMF, …)
            n3=self.state.current_config.areas[0].networks.n3,          # GTP tunnel to gNB
            n6=self.state.current_config.areas[0].networks.n6,          # Data-network side
            gnb=self.state.current_config.areas[0].networks.gnb         # gNB management network
        )
        self.state.core_vm_networks_mapping = vm_networks
        return vm_networks

    def _create_core_vm(self, vm_networks: BlueCreateModelNetworks) -> VmResource:
        """
        Creates the virtual machine that will host the Amarisoft core, registers
        it with the framework, and waits for it to be ready.

        Port security is disabled because Amarisoft performs NAT for UE traffic,
        which requires forwarding packets whose source address falls outside the
        VM's own IP range.

        Args:
            vm_networks: Network mapping produced by ``_build_network_mapping``.

        Returns:
            The created and registered VmResource.
        """
        virtual_machine = VmResource(
            area=self.state.current_config.areas[0].id,
            name=f"{self.id.lower()}-AmarisoftCore",
            image=VmResourceImage(name=BASE_IMAGE24, url=BASE_IMAGE24_URL),
            flavor=DEFAULT_FLAVOR,
            username="ubuntu",
            password=self.state.current_config.config.default_password or "ubuntu",
            management_network=vm_networks.mgt.net_name,
            additional_networks=[vm_networks.n4.net_name, vm_networks.n3.net_name, vm_networks.n6.net_name],
            require_port_security_disabled=True,  # Required for UE NAT traffic
            resource_group=self.id
        )
        self.state.core_vm = virtual_machine
        self.register_resource(virtual_machine)
        self.provider.create_vm(virtual_machine)
        return virtual_machine

    def _install_amarisoft(self, virtual_machine: VmResource):
        """
        Runs the Amarisoft installation playbook on the core VM.

        The playbook downloads the Amarisoft tarball from the internal mirror,
        extracts it, and runs the vendor install script with the correct flags.

        Args:
            virtual_machine: The VM on which Amarisoft will be installed.
        """
        installator = AmarisoftInstallator(
            vm_resource=virtual_machine,
            amarisoft_tar_url="https://images.tnt-lab.unige.it/private/AmariSoft/amarisoft.2026-03-13.tar.gz",
            resource_group=self.id
        )
        self.state.core_vm_installer = installator
        self.register_resource(installator)
        self.provider.configure_vm(installator)

    def _deploy_router(self, area_id: int, vm_networks: BlueCreateModelNetworks) -> Router5GNetworkInfo:
        """
        Deploys a Router5G child blueprint and retrieves its network information.

        The router handles gNB-facing IP routing and provides the N3/N6 gateway
        addresses that the Amarisoft configuration needs (for the ``routes``
        systemd service installed on the core VM).

        Args:
            area_id:     The area where the router will be placed.
            vm_networks: Network mapping used to configure the router interfaces.

        Returns:
            Router5GNetworkInfo with N3/N6/gNB IPs and the gNB CIDR.
        """
        router_create_model = Router5GCreateModel(
            area_id=area_id,
            networks=Router5GCreateModelNetworks(
                mgt=vm_networks.mgt,
                gnb=vm_networks.gnb,
                core=vm_networks.n4,
                n3=vm_networks.n3,
                n6=vm_networks.n6
            )
        )
        router_id = self.provider.create_blueprint(ROUTER_BLUEPRINT_TYPE, router_create_model)
        self.register_children(router_id)
        router_info: Router5GNetworkInfo = self.provider.call_blueprint_function(router_id, ROUTER_GET_INFO_FUNCTION)
        self.logger.info("Deployed router")
        return router_info

    def _build_upf_info(
        self,
        area_id: int,
        served_slices: list[Slice5GWithDNNs],
        vm_networks: BlueCreateModelNetworks,
        router_info: Router5GNetworkInfo
    ):
        """
        Constructs the UPFInfo representing the Amarisoft integrated UPF and
        stores it in state.

        Because Amarisoft handles user-plane forwarding internally there is no
        separate UPF VM. Network info is therefore derived from the core VM's
        interfaces. The N6 CIDR and IP are placeholder values: Amarisoft
        performs NAT internally and does not expose a real N6 interface on the
        VM (see ``_N6_PLACEHOLDER_*`` module constants).

        The ``UPFBlueCreateModel`` in ``current_config`` is intentionally dummy
        data used only to satisfy required Pydantic fields; it is never read by
        any day-2 operation.

        Args:
            area_id:       Area ID for this deployment.
            served_slices: Slices (with DNNs) that this core will serve.
            vm_networks:   Network mapping of the core VM.
            router_info:   Network info returned by the Router5G blueprint.
        """
        deployed_upf_info = DeployedUPFInfo(
            area=area_id,
            served_slices=served_slices,
            network_info=UPFNetworkInfo(
                n4_cidr=SerializableIPv4Network(self.state.core_vm.network_interfaces[vm_networks.n4.net_name][0].fixed.cidr),
                n3_cidr=SerializableIPv4Network(self.state.core_vm.network_interfaces[vm_networks.n3.net_name][0].fixed.cidr),
                n6_cidr=SerializableIPv4Network(_N6_PLACEHOLDER_CIDR),  # No real N6 interface; Amarisoft uses internal NAT
                n4_ip=SerializableIPv4Address(self.state.core_vm.network_interfaces[vm_networks.n4.net_name][0].fixed.ip),
                n3_ip=SerializableIPv4Address(self.state.core_vm.network_interfaces[vm_networks.n3.net_name][0].fixed.ip),
                n6_ip=SerializableIPv4Address(_N6_PLACEHOLDER_IP),      # No real N6 interface; Amarisoft uses internal NAT
            ),
            router_gnb_ip=router_info.gnb_ip
        )

        # Blue ID is starting with 000 -> reserved, not assigned automatically to other blueprints.
        # This is a fake ID that is used only to satisfy the UPFInfo model.
        self.state.upf_info = UPFInfo(
            blue_id="000000",
            router_gnb_ip=deployed_upf_info.router_gnb_ip.exploded if deployed_upf_info.router_gnb_ip else None,
            external=False,
            upf_list=[deployed_upf_info],
            # Dummy create model — satisfies required fields only, never read
            current_config=UPFBlueCreateModel(area_id=area_id, networks=vm_networks)
        )

    def _configure_core(
        self,
        virtual_machine: VmResource,
        vm_networks: BlueCreateModelNetworks,
        router_info: Router5GNetworkInfo
    ):
        """
        Creates the AmarisoftConfigurator, registers it, and applies the initial
        configuration to the core VM via Ansible.

        The configurator is saved to state so that day-2 operations can re-invoke
        it without rebuilding it from scratch.

        Args:
            virtual_machine: The core VM to configure.
            vm_networks:     Network mapping; provides the N3 IP for GPT binding.
            router_info:     Router network info; provides the gNB CIDR and N3/N6
                             gateway addresses for the ``routes`` systemd service.
        """
        configurator = AmarisoftConfigurator(
            vm_resource=virtual_machine,
            amarisoft_5g_state=self.state,
            gpt_bind_address=virtual_machine.network_interfaces[vm_networks.n3.net_name][0].fixed.ip,
            license_server_addr=str(self.state.current_config.config.licence_server),
            gnb_cidr=router_info.gnb_cidr.with_prefixlen,
            n3_gateway=router_info.n3_ip.exploded,
            n6_gateway=router_info.n6_ip.exploded,
            resource_group=self.id
        )
        self.state.core_vm_configurator = configurator
        self.register_resource(configurator)
        self.provider.configure_vm(configurator)

        subscriber_configurator = AmarisoftSubscriberConfigurator(
            vm_resource=virtual_machine,
            amarisoft_5g_state=self.state,
            resource_group=self.id
        )
        self.state.core_vm_subscriber_configurator = subscriber_configurator
        self.register_resource(subscriber_configurator)

    # -------------------------------------------------------------------------
    # Edge areas
    # -------------------------------------------------------------------------

    def update_edge_areas(self, force: bool = False):
        """
        Registers or refreshes edge-area entries in the parent-class state.

        Amarisoft does not support external UPFs: the integrated UPF inside the
        core VM serves all traffic, so at most one edge area can exist.

        On the first call (day-0) the edge area is created and the stored
        ``upf_info`` is attached to it. Subsequent calls (day-2) currently emit
        a warning because dynamic edge-area updates are not yet implemented.

        Args:
            force: Reserved for future use (force reconfiguration of an already-
                   deployed edge area).

        Raises:
            NFVCLCoreException: if more than one edge area would need to exist.
        """
        for area in self.state.current_config.areas:
            if len(self.state.edge_areas) > 1:
                raise NFVCLCoreException("Amarisoft does not support external UPF. Only one area is supported for now!")
            if str(area.id) not in self.state.edge_areas:
                self.state.edge_areas[str(area.id)] = EdgeAreaInfo(area=area.id)
                self.state.edge_areas[str(area.id)].upf = self.state.upf_info
            else:
                self.logger.warning("Edge area update has not been implemented yet")

    # -------------------------------------------------------------------------
    # Day-2: subscribers
    # -------------------------------------------------------------------------

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        """
        We DO NOT CALL THE PARENT METHOD HERE. We don't want to call self.update_core() as done in the parent class.

        Adds one or more subscribers to the state and pushes the updated
        UE-DB configuration to the core VM.
        """
        self.state.core_vm_subscriber_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_subscriber_configurator)

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        """
        We DO NOT CALL THE PARENT METHOD HERE. We don't want to call self.update_core() as done in the parent class.

        Removes one or more subscribers from the state and pushes the updated
        UE-DB configuration to the core VM.
        """
        self.state.core_vm_subscriber_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_subscriber_configurator)

    # -------------------------------------------------------------------------
    # Day-2: TAC
    # -------------------------------------------------------------------------

    def add_tac(self, add_area_model: Core5GAddTacModel):
        raise NFVCLCoreException("Add TAC is not supported in the Amarisoft blueprint")

    def del_tac(self, del_area_model: Core5GDelTacModel):
        raise NFVCLCoreException("Delete TAC is not supported in the Amarisoft blueprint")

    # -------------------------------------------------------------------------
    # Day-2: slices
    # -------------------------------------------------------------------------

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        """
        We DO NOT CALL THE PARENT METHOD HERE. We don't want to call self.update_core(),self.update_edge_areas(),self.update_gnb_config()  as done in the parent class.

        Adds a slice to the state and pushes the updated MME configuration
        to the core VM.
        """
        self.state.core_vm_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_configurator)

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        """
        We DO NOT CALL THE PARENT METHOD HERE. We don't want to call self.update_core(),self.update_edge_areas(),self.update_gnb_config()  as done in the parent class.

        Removes a slice from the state and pushes the updated MME configuration
        to the core VM.
        """
        self.state.core_vm_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_configurator)

    # -------------------------------------------------------------------------
    # Day-2: DNNs
    # -------------------------------------------------------------------------

    def add_dnn(self, dnn_model: Core5GAddDnnModel):
        """
        Adds a DNN to the state, pushes the updated configuration, and refreshes
        edge-area UPF info so downstream components see the new data network.
        """
        self.state.core_vm_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_configurator)
        self.update_edge_areas()

    def del_dnn(self, del_dnn_model: Core5GDelDnnModel):
        """
        Removes a DNN from the state, pushes the updated configuration, and
        refreshes edge-area UPF info.
        """
        self.state.core_vm_configurator.amarisoft_5g_state = self.state
        self.provider.configure_vm(self.state.core_vm_configurator)
        self.update_edge_areas()

    # -------------------------------------------------------------------------
    # Day-2: general
    # -------------------------------------------------------------------------

    def update_core(self):
        """Re-applies the full Amarisoft configuration to the core VM."""
        self.provider.configure_vm(self.state.core_vm_configurator)

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------

    def get_amf_ip(self) -> str:
        """
        Returns the AMF IP address (the core VM's N3 interface IP).

        Amarisoft exposes the AMF on the same interface used for GTP (N3),
        so this is the address that gNBs use to reach the core.
        """
        return self.state.core_vm.network_interfaces[self.state.core_vm_networks_mapping.n3.net_name][0].fixed.ip

    def get_nrf_ip(self) -> str:
        """Not applicable: Amarisoft is a combined core with no separate NRF."""
        pass

    def wait_core_ready(self):
        """
        Hook called after ``create_5g`` completes. No active health-check is
        implemented: the Ansible playbook already confirms that configuration
        has been successfully applied before returning.
        """
        pass

    def get_slice(self, slice_id: str) -> SubSliceProfiles:
        """
        Returns the slice profile with the given slice ID.

        Args:
            slice_id: Slice ID to look up.

        Returns:
            The matching SubSliceProfiles entry.

        Raises:
            ValueError: if no slice with that ID exists in the current config.
        """
        for _slice in self.state.current_config.config.sliceProfiles:
            if _slice.sliceId == slice_id:
                return _slice
        raise ValueError(f'Slice {slice_id} not found.')

    def get_subscriber(self, imsi: str) -> SubSubscribers:
        """
        Returns the subscriber with the given IMSI.

        Args:
            imsi: IMSI to look up.

        Returns:
            The matching SubSubscribers entry.

        Raises:
            ValueError: if no subscriber with that IMSI exists.
        """
        for _subscriber in self.state.current_config.config.subscribers:
            if _subscriber.imsi == imsi:
                return _subscriber
        raise ValueError(f'Subscriber with imsi: {imsi} not found.')

    def get_area(self, area_id: int) -> SubArea:
        """
        Returns the area with the given area ID.

        Args:
            area_id: Area ID to look up.

        Returns:
            The matching SubArea entry.

        Raises:
            ValueError: if no area with that ID exists.
        """
        for area in self.state.current_config.areas:
            if area_id == area.id:
                return area
        raise ValueError(f'Area {area_id} not found.')

    def get_area_from_sliceid(self, sliceid: str) -> SubArea:
        """
        Returns the area that contains the slice with the given slice ID.

        Args:
            sliceid: Slice ID to search for.

        Returns:
            The SubArea that contains the matching slice.

        Raises:
            ValueError: if no area contains a slice with that ID.
        """
        for area in self.state.current_config.areas:
            for _slice in area.slices:
                if _slice.sliceId == sliceid:
                    return area
        raise ValueError(f'Area of slice {sliceid} not found.')

    def get_dnn(self, dnn_name: str) -> SubDataNets:
        """
        Returns the data network configuration with the given DNN name.

        Args:
            dnn_name: DNN name to look up.

        Returns:
            The matching SubDataNets entry.

        Raises:
            ValueError: if no DNN with that name exists.
        """
        for dnn in self.state.current_config.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        raise ValueError(f'Dnn {dnn_name} not found.')
