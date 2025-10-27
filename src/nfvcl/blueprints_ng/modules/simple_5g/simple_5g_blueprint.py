from typing import Dict, Optional, List

from pydantic import Field

from nfvcl_core.blueprints.blueprint_ng import BlueprintNGState, BlueprintNG
from nfvcl_core.blueprints.blueprint_type_manager import blueprint_type
from nfvcl_core.managers import get_kubernetes_manager
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.resources import NetResource, NetResourcePool
from nfvcl_models.blueprint_ng.blueprint_ueransim_model import UeransimConfig, UeransimNetworkEndpoints, UeransimArea, UeransimUe
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel, SubConfig, NetworkEndPoints, NetworkEndPoint, NetworkEndPointWithType, SubDataNets, Pool, SubSliceProfiles, SubProfileParams, SubSubscribers, SubSnssai, SubArea, SubAreaNetwork, SubSlices
from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_models.blueprint_ng.g5.custom_types_5g import PDUSessionType
from nfvcl_models.blueprint_ng.g5.ue import UESim, OpType, UESession
from nfvcl_models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance
from nfvcl_models.blueprint_ng.k8s.k8s_rest_models import K8sCreateModel, K8sAreaDeployment
from nfvcl_models.blueprint_ng.simple_5g.simple_5g_rest_models import Simple5GCreateModel


class AreaState(NFVCLBaseModel):
    area_id: int
    ues: Optional[List[UeransimUe]] = Field(default_factory=list)
    n3_network: Optional[NetResource] = Field(default=None)
    n6_network: Optional[NetResource] = Field(default=None)
    gnb_network: Optional[NetResource] = Field(default=None)
    data_network: Optional[NetResource] = Field(default=None)
    core_blueprint_id: Optional[str] = Field(default=None)


class Simple5GBlueprintNGState(BlueprintNGState):
    area_states: Dict[str, AreaState] = Field(default_factory=dict)
    k8s_blueprint_id: Optional[str] = Field(default=None)
    ueransim_blueprint_id: Optional[str] = Field(default=None)


@blueprint_type("simple_5g")
class Simple5GBlueprint(BlueprintNG[Simple5GBlueprintNGState, Simple5GCreateModel]):
    N3_NETWORK_TEMPLATE = "10.111.3.0/24"
    N6_NETWORK_TEMPLATE = "10.111.6.0/24"
    GNB_NETWORK_TEMPLATE = "10.111.100.0/24"
    DATA_NETWORK_TEMPLATE = "10.111.200.0/24"
    DATA_NETWORK_POOL_START = "10.111.200.100"
    DATA_NETWORK_POOL_END = "10.111.200.200"

    def __init__(self, blueprint_id: str, state_type: type[BlueprintNGState] = Simple5GBlueprintNGState):
        """
        Don't write code in the init method, this will be called every time the blueprint is loaded from the DB
        """
        super().__init__(blueprint_id, state_type)

    def create(self, create_model: Simple5GCreateModel):
        super().create(create_model)
        self.logger.info("Starting creation of simple_5g blueprint")
        self.net_name_n3 = f"n3_{self.id}"
        self.net_name_n6 = f"n6_{self.id}"
        self.net_name_gnb = f"gnb_{self.id}"
        self.net_name_data = f"data_{self.id}"


        # 1. Create networks for each area (N3, N6, gNB and data networks)
        self._create_networks(create_model)

        # 2. Create K8s blueprint with workers in the areas
        self._create_k8s_blueprint(create_model)

        # 3. Create UERANSIM blueprint
        self._create_ueransim_blueprint(create_model)

        # 4. Create core blueprints for each area
        self._create_core_blueprints(create_model)

        self.logger.info(f"Simple 5G blueprint created successfully")

    def destroy(self):
        # The core need to be destroyed first, otherwise we are not able to delete the k8s blueprint
        for key, val in self.state.area_states.items():
            if val.core_blueprint_id:
                self.provider.delete_blueprint(val.core_blueprint_id)
                self.deregister_children(val.core_blueprint_id)
        super().destroy()

    def _create_networks(self, create_model: Simple5GCreateModel):
        """Create N3, N6, gNB and data networks in each area with different subnets"""
        self.logger.info("Creating networks for each area...")

        already_created_nets = []

        # Initialize area states dict
        for i, area in enumerate(create_model.areas):
            self.state.area_states[str(area.id)] = AreaState(area_id=area.id)
            vim = self.provider.topology_manager.get_vim_from_area_id_model(area.id)
            net_id = f"{vim.name}_{self.net_name_n3}"
            if net_id not in already_created_nets:
                net_res = NetResource(area=area.id, name=self.net_name_n3, cidr=self.N3_NETWORK_TEMPLATE)
                self.register_resource(net_res)
                self.provider.create_net(net_res)
                already_created_nets.append(net_id)
            else:
                self.logger.warning(f"Network {net_id} already exists on this VIM, skipping creation.")

            net_id = f"{vim.name}_{self.net_name_n6}"
            if net_id not in already_created_nets:
                net_res = NetResource(area=area.id, name=self.net_name_n6, cidr=self.N6_NETWORK_TEMPLATE)
                self.register_resource(net_res)
                self.provider.create_net(net_res)
                already_created_nets.append(net_id)
            else:
                self.logger.warning(f"Network {net_id} already exists on this VIM, skipping creation.")

            net_id = f"{vim.name}_{self.net_name_gnb}"
            if net_id not in already_created_nets:
                net_res = NetResource(area=area.id, name=self.net_name_gnb, cidr=self.GNB_NETWORK_TEMPLATE)
                self.register_resource(net_res)
                self.provider.create_net(net_res)
                already_created_nets.append(net_id)
            else:
                self.logger.warning(f"Network {net_id} already exists on this VIM, skipping creation.")

            net_id = f"{vim.name}_{self.net_name_data}"
            if net_id not in already_created_nets:
                net_res = NetResource(
                    area=area.id,
                    name=self.net_name_data,
                    cidr=self.DATA_NETWORK_TEMPLATE,
                    allocation_pool=NetResourcePool(start=SerializableIPv4Address(self.DATA_NETWORK_POOL_START), end=SerializableIPv4Address(self.DATA_NETWORK_POOL_END))
                )
                self.register_resource(net_res)
                self.provider.create_net(net_res)
                already_created_nets.append(net_id)
            else:
                self.logger.warning(f"Network {net_id} already exists on this VIM, skipping creation.")

            self.logger.info(f"Created networks for area {area}")

    def _create_k8s_blueprint(self, create_model: Simple5GCreateModel):
        """Create Kubernetes blueprint with workers in the specified areas"""
        self.logger.info("Creating Kubernetes blueprint...")

        k8s_areas: List[K8sAreaDeployment] = []

        first = True
        index = 1

        for area in create_model.areas:

            lb_ips_area = []
            for i in range(9):
                lb_ips_area.append(f"10.111.200.{index}{i}")

            k8s_areas.append(
                K8sAreaDeployment(
                    area_id=area.id,
                    mgmt_net=create_model.mgmt_net,
                    worker_flavors=area.workers.flavor,
                    worker_replicas=area.workers.replicas,
                    is_master_area=first,  # First area is the master
                    additional_networks=[f"data_{self.id}"],
                    load_balancer_pools_ips=[SerializableIPv4Address(ip) for ip in lb_ips_area],
                )
            )
            first = False
            index += 1


        k8s_create_model = K8sCreateModel(
            areas=k8s_areas,
        )

        blueprint_id = self.provider.create_blueprint("k8s", k8s_create_model)
        self.register_children(blueprint_id)
        self.state.k8s_blueprint_id = blueprint_id
        self.logger.info(f"Created Kubernetes blueprint with ID: {blueprint_id}")

        if create_model.force_pods_on_area:
            get_kubernetes_manager().install_nfvcl_admission_webhook(blueprint_id)


    def _create_ueransim_blueprint(self, create_model: Simple5GCreateModel):
        """Create UERANSIM blueprint for the 5G setup"""
        self.logger.info("Creating UERANSIM blueprint...")

        slice = Slice5G(
            sst=1,
            sd=1
        )

        # Prepare UERANSIM configuration for each area
        ueransim_areas = []
        for area in create_model.areas:
            area_id = area.id

            ues: List[UeransimUe] = []
            for i in range(area.num_ues):
                ue = UeransimUe(
                    id=i + 1,  # UE IDs start from 1
                    sims=[
                        UESim(
                            imsi=f"00101{area_id+i+1:010d}",
                            plmn="00101",
                            key="814BCB2AEBDA557AEEF021BB21BEFE25",
                            op="9B5DA0D4EC1E2D091A6B47E3B91D2496",
                            opType=OpType.OPC,
                            amf=8000,
                            configured_nssai=[slice],
                            default_nssai=[slice],
                            sessions=[
                                UESession(
                                    type=PDUSessionType.IPv4,
                                    dnn="internet",
                                    slice=slice
                                )
                            ]
                        )
                    ]
                )
                ues.append(ue)
                self.state.area_states[str(area_id)].ues.append(ue)


            ueransim_area = UeransimArea(
                id=area_id,
                nci="0x00000002",
                idLength=32,
                ues=ues
            )

            ueransim_areas.append(ueransim_area)


        # Create UERANSIM blueprint
        ueransim_create_model = UeransimBlueprintRequestInstance(
            config=UeransimConfig(network_endpoints=UeransimNetworkEndpoints(
                mgt=create_model.mgmt_net,
                n2=self.net_name_data,
                n3=self.net_name_gnb
            )),
            areas=ueransim_areas
        )

        blueprint_id = self.provider.create_blueprint("ueransim", ueransim_create_model)
        self.register_children(blueprint_id)
        self.state.ueransim_blueprint_id = blueprint_id
        self.logger.info(f"Created UERANSIM blueprint with ID: {blueprint_id}")


    def _create_core_blueprints(self, create_model: Simple5GCreateModel):
        """Create 5G core blueprint for each area based on specified implementation"""
        self.logger.info("Creating 5G core blueprints...")

        for area in create_model.areas:
            area_id = area.id

            subscribers: List[SubSubscribers] = []
            for ue in self.state.area_states[str(area_id)].ues:
                sim = ue.sims[0]
                subscribers.append(
                    SubSubscribers(
                        imsi=sim.imsi,
                        k=sim.key,
                        opc=sim.op,
                        authenticationMethod="5G_AKA",
                        authenticationManagementField="9001",
                        snssai=[
                            SubSnssai(sliceId="000001", sliceType="EMBB", default_slice=True)
                        ]
                    )
                )


            # Create core blueprint
            core_create_model = Create5gModel(
                config=SubConfig(
                    network_endpoints=NetworkEndPoints(
                        mgt=NetworkEndPoint(net_name=create_model.mgmt_net),
                        n2=NetworkEndPointWithType(net_name=self.net_name_data),
                        n4=NetworkEndPointWithType(net_name=self.net_name_data),
                        data_nets=[SubDataNets(net_name="internet", dnn="internet", dns="8.8.8.8", pools=[Pool(cidr="10.250.0.0/16")], uplinkAmbr="1000 Mbps", downlinkAmbr="1000 Mbps", default5qi="9")],
                    ),
                    plmn="00101",
                    sliceProfiles=[
                        SubSliceProfiles(
                            sliceId="000001",
                            sliceType="EMBB",
                            dnnList=["internet"],
                            profileParams=SubProfileParams(
                                isolationLevel="ISOLATION",
                                sliceAmbr="1000 Mbps",
                                ueAmbr="1000 Mbps",
                                maximumNumberUE=10
                            ),
                        )
                    ],
                    subscribers=subscribers
                ),
                areas=[
                    SubArea(
                        id=area_id,
                        nci="0x00000002",
                        idLength=32,
                        core=True,
                        networks=SubAreaNetwork(
                            n3=NetworkEndPointWithType(net_name=self.net_name_n3),
                            n6=NetworkEndPointWithType(net_name=self.net_name_n6),
                            gnb=NetworkEndPointWithType(net_name=self.net_name_gnb),
                        ),
                        slices=[SubSlices(sliceId=1, sliceType="EMBB")],
                    )
                ]
            )

            blueprint_id = self.provider.create_blueprint(area.core_implementation, core_create_model)
            self.register_children(blueprint_id)
            self.state.area_states[str(area_id)].core_blueprint_id = blueprint_id
            self.logger.info(f"Created {area.core_implementation} blueprint for area {area_id} with ID: {blueprint_id}")

