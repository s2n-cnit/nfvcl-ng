import time
from typing import ClassVar

import pytest
from pytest_dependency import depends

from tests.blueprints.blue5g.context_5g import FiveGTestContext
from tests.blueprints.blue5g.create_configs import UERANSIM_DAY2_SLICE_SIM
from tests.blueprints.blue5g.parent5g_test import NFVCL5GTestSuite
from tests.blueprints.ueransim_utils import UeransimSSH
from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core_models.network.network_models import PduType
from nfvcl_models.blueprint_ng.g5.core import (
    Core5GAddDnnModel,
    Core5GAddSliceModel,
    Core5GAddSubscriberModel,
    Core5GAddTacModel,
    Core5GDelDnnModel,
    Core5GDelSliceModel,
    Core5GDelSubscriberModel,
    Core5GDelTacModel,
)
from nfvcl_models.blueprint_ng.g5.ue import UESim
from nfvcl_models.blueprint_ng.g5.ueransim import (
    UeransimBlueprintRequestAddSim,
    UeransimBlueprintRequestDelSim,
)

DAY2_EXISTING_SLICE_ID = "000001"
DAY2_ADDED_SLICE_ID = "000002"
DAY2_AREA_SLICE_ID = "000003"
DAY2_AREA_SLICE_TAI = "00101000002"
DAY2_ADDED_DNN = "dnn2"
DAY2_ADDED_DNN_CIDR = "12.169.0.0/16"
DAY2_AREA_DNN = "dnn3"
DAY2_AREA_DNN_CIDR = "12.170.0.0/16"
DAY2_ADDED_AREA_ID = 2
DAY2_ADDED_SUBSCRIBER_IMSI = "001014000000002"
DAY2_AREA_SUBSCRIBER_IMSI = "001014000000003"
DAY2_SUBSCRIBER_KEY = "814BCB2AEBDA557AEEF021BB21BEFE25"
DAY2_SUBSCRIBER_OPC = "9B5DA0D4EC1E2D091A6B47E3B91D2496"
DAY2_SLICE_SIM = UESim.model_validate(UERANSIM_DAY2_SLICE_SIM)
DAY2_SLICE_SUBSCRIBER_IMSI = DAY2_SLICE_SIM.imsi

pytestmark = pytest.mark.integration


def _subscriber_model(imsi: str, slice_id: str = DAY2_EXISTING_SLICE_ID) -> Core5GAddSubscriberModel:
    return Core5GAddSubscriberModel.model_validate(
        {
            "imsi": imsi,
            "k": DAY2_SUBSCRIBER_KEY,
            "opc": DAY2_SUBSCRIBER_OPC,
            "snssai": [
                {
                    "sliceId": slice_id,
                    "sliceType": "EMBB",
                    "pduSessionIds": [
                        "1"
                    ],
                    "default_slice": True
                }
            ],
            "authenticationMethod": "5G_AKA",
            "authenticationManagementField": "8000"
        }
    )


def _dnn_model() -> Core5GAddDnnModel:
    return Core5GAddDnnModel.model_validate(
        {
            "net_name": DAY2_ADDED_DNN,
            "dnn": DAY2_ADDED_DNN,
            "dns": "8.8.8.8",
            "pools": [
                {
                    "cidr": DAY2_ADDED_DNN_CIDR
                }
            ],
            "uplinkAmbr": "100 Mbps",
            "downlinkAmbr": "100 Mbps",
            "default5qi": "9"
        }
    )


def _slice_model() -> Core5GAddSliceModel:
    return Core5GAddSliceModel.model_validate(
        {
            "sliceId": DAY2_ADDED_SLICE_ID,
            "sliceType": "EMBB",
            "dnnList": [DAY2_ADDED_DNN],
            "profileParams": {
                "isolationLevel": "ISOLATION",
                "sliceAmbr": "1000 Mbps",
                "ueAmbr": "50 Mbps",
                "maximumNumberUE": 10,
                "pduSessions": [
                    {
                        "pduSessionId": "1",
                        "pduSessionAmbr": "20 Mbps",
                        "flows": [
                            {
                                "flowId": "1",
                                "ipAddrFilter": "8.8.4.4",
                                "qi": "9",
                                "gfbr": "10 Mbps"
                            }
                        ]
                    }
                ]
            },
            "locationConstraints": [
                {
                    "geographicalAreaId": "1",
                    "tai": "00101000001"
                }
            ],
            "enabledUEList": [
                {
                    "ICCID": "*"
                }
            ],
            "area_ids": [
                "1"
            ]
        }
    )


def _area_slice_model() -> Core5GAddSliceModel:
    slice_data = _slice_model().model_dump(by_alias=True)
    slice_data.update(
        {
            "sliceId": DAY2_AREA_SLICE_ID,
            "dnnList": [DAY2_AREA_DNN],
            "locationConstraints": [
                {
                    "geographicalAreaId": str(DAY2_ADDED_AREA_ID),
                    "tai": DAY2_AREA_SLICE_TAI,
                }
            ],
            "area_ids": None,
        }
    )
    return Core5GAddSliceModel.model_validate(slice_data)


def _area_dnn_model() -> Core5GAddDnnModel:
    dnn_data = _dnn_model().model_dump(by_alias=True)
    dnn_data.update(
        {
            "net_name": DAY2_AREA_DNN,
            "dnn": DAY2_AREA_DNN,
            "pools": [{"cidr": DAY2_AREA_DNN_CIDR}],
        }
    )
    return Core5GAddDnnModel.model_validate(dnn_data)


class Generic5GCoreTestSuite(NFVCL5GTestSuite):
    CORE_TYPE: ClassVar[str]
    ADD_SUBSCRIBER_WAIT_SECONDS: ClassVar[int] = 0
    DELETE_SUBSCRIBER_WAIT_SECONDS: ClassVar[int] = 0
    ADD_SLICE_WAIT_SECONDS: ClassVar[int] = 10
    DELETE_SLICE_WAIT_SECONDS: ClassVar[int] = 0
    ADD_AREA_WAIT_SECONDS: ClassVar[int] = 0
    DELETE_AREA_WAIT_SECONDS: ClassVar[int] = 0

    @pytest.fixture(scope="class", autouse=True)
    def _cleanup_core_deployments(self, nfvcl: NFVCL, context_5g: FiveGTestContext):
        yield

        if context_5g.ueransim1 is not None:
            ueransim1_sims = context_5g.ueransim1.state.areas["1"].ues[0].vm_ue_configurator.sims
            if any(sim.imsi == DAY2_SLICE_SUBSCRIBER_IMSI for sim in ueransim1_sims):
                nfvcl.update_blueprint(
                    context_5g.ueransim1_bp_id,
                    "ueransim/del_sim",
                    UeransimBlueprintRequestDelSim(
                        area_id="1",
                        ue_id=1,
                        imsi=DAY2_SLICE_SUBSCRIBER_IMSI,
                    ),
                )
        if context_5g.core_bp_id is not None:
            nfvcl.delete_blueprint(context_5g.core_bp_id)
        if context_5g.ueransim2_bp_id is not None:
            nfvcl.delete_blueprint(context_5g.ueransim2_bp_id)

        context_5g.core_bp_id = None
        context_5g.core = None
        context_5g.ueransim2_bp_id = None
        context_5g.ueransim2 = None
        context_5g.ueransim2_ue_ssh = None
        context_5g.ueransim2_gnb_ssh = None

    @pytest.fixture(autouse=True)
    def _require_core_deployment(self, request: pytest.FixtureRequest):
        if request.node.name in {"test_check_ueransim_connection", "test_deploy_core"}:
            return

        depends(request, ["test_deploy_core"], scope="class")

    def _day2_path(self, operation: str) -> str:
        return f"{self.CORE_TYPE}/{operation}"

    @staticmethod
    def _wait_for_reconfiguration(delay_seconds: int) -> None:
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    def test_check_ueransim_connection(self):
        assert len(self.context_5g.ueransim1.state.areas) == 1

        self.context_5g.ueransim_ue_ssh = UeransimSSH(self.context_5g.ueransim1.state.areas["1"].ues[0].vm_ue.access_ip)
        self.context_5g.ueransim_gnb_ssh = UeransimSSH(self.context_5g.ueransim1.state.areas["1"].vm_gnb.access_ip)
        # TODO check connection

    def test_deploy_core(self):
        gnb_pdus = [
            pdu
            for pdu in self.nfvcl.get_pdus()
            if pdu.type == PduType.GNB and pdu.instance_type == "UERANSIM"
        ]
        assert len(gnb_pdus) == 1

        core_area = self.context_5g.core_5g_create_model.areas[0]
        assert core_area.gnb is not None
        if core_area.gnb.pduList is None:
            core_area.gnb.pduList = []
        if gnb_pdus[0].name not in core_area.gnb.pduList:
            core_area.gnb.pduList.append(gnb_pdus[0].name)

        self.context_5g.core_bp_id = self.nfvcl.create_blueprint(
            self.CORE_TYPE,
            self.context_5g.core_5g_create_model,
        )
        assert self.context_5g.core_bp_id is not None
        self.context_5g.core = self.nfvcl.blueprint_manager.get_blueprint_instance(self.context_5g.core_bp_id)

    # def test_check_core(self):
    #     pass
    # def test_check_routers(self):
    #     pass
    # def test_check_upfs(self):
    #     pass
    # def test_check_gnbs_configuration(self):
    #     pass

    def test_check_gnb_amf_connection(self):
        assert self.context_5g.ueransim_gnb_ssh.check_gnb_connection()

    # def test_check_upf_smf_connection(self):
    #     pass
    # def test_check_router_upf_connectivity(self):
    #     pass
    # def test_check_router_gnb_connectivity(self):
    #     pass

    def check_ue_connectivity(self, imsi: str, retries: int = 1, time_between_retries: int = 1) -> bool:
        for attempt in range(retries):
            self.context_5g.ueransim_ue_ssh.restart_ue_service(imsi)

            if self.context_5g.ueransim_ue_ssh.check_ue_registered(imsi, timeout=20):
                if self.context_5g.ueransim_ue_ssh.check_ue_connectivity(imsi, "1.1.1.1"):
                    return True

            if attempt < retries - 1:
                time.sleep(time_between_retries)

        return False

    def test_check_ue_connectivity(self):
        assert self.check_ue_connectivity("001014000000001", retries=3, time_between_retries=20)

    def test_add_subscriber(self):
        assert len(self.context_5g.core.state.current_config.config.subscribers) == 1
        assert not self.check_ue_connectivity(DAY2_ADDED_SUBSCRIBER_IMSI)
        new_ue = _subscriber_model(DAY2_ADDED_SUBSCRIBER_IMSI)
        self.nfvcl.update_blueprint(self.context_5g.core_bp_id, self._day2_path("add_ues"), new_ue)
        self._wait_for_reconfiguration(self.ADD_SUBSCRIBER_WAIT_SECONDS)
        assert len(self.context_5g.core.state.current_config.config.subscribers) == 2
        assert self.check_ue_connectivity(DAY2_ADDED_SUBSCRIBER_IMSI, retries=4, time_between_retries=30)

    def test_del_subscriber(self):
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_ADDED_SUBSCRIBER_IMSI) is not None
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_ues"),
            Core5GDelSubscriberModel(imsi=DAY2_ADDED_SUBSCRIBER_IMSI),
        )
        self._wait_for_reconfiguration(self.DELETE_SUBSCRIBER_WAIT_SECONDS)
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_ADDED_SUBSCRIBER_IMSI) is None
        assert len(self.context_5g.core.state.current_config.config.subscribers) == 1
        assert not self.check_ue_connectivity(DAY2_ADDED_SUBSCRIBER_IMSI)

    def test_add_slice(self):
        assert self.context_5g.core.state.current_config.get_slice_profile(DAY2_ADDED_SLICE_ID) is None
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_ADDED_DNN) is None

        self.nfvcl.update_blueprint(self.context_5g.core_bp_id, self._day2_path("add_dnn"), _dnn_model())
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("add_slice_operator"),
            _slice_model(),
        )

        added_slice = self.context_5g.core.state.current_config.get_slice_profile(DAY2_ADDED_SLICE_ID)
        area = self.context_5g.core.state.current_config.get_area(1)
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_ADDED_DNN) is not None
        assert added_slice is not None
        assert added_slice.dnnList == [DAY2_ADDED_DNN]
        assert any(area_slice.sliceId == DAY2_ADDED_SLICE_ID for area_slice in area.slices)

        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("add_ues"),
            _subscriber_model(DAY2_SLICE_SUBSCRIBER_IMSI, DAY2_ADDED_SLICE_ID),
        )
        self.nfvcl.update_blueprint(
            self.context_5g.ueransim1_bp_id,
            "ueransim/add_sim",
            UeransimBlueprintRequestAddSim(
                area_id="1",
                ue_id=1,
                sim=DAY2_SLICE_SIM,
            ),
        )
        self._wait_for_reconfiguration(self.ADD_SLICE_WAIT_SECONDS)
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_SLICE_SUBSCRIBER_IMSI) is not None
        assert any(
            sim.imsi == DAY2_SLICE_SUBSCRIBER_IMSI
            for sim in self.context_5g.ueransim1.state.areas["1"].ues[0].vm_ue_configurator.sims
        )
        assert self.check_ue_connectivity("001014000000001", retries=3, time_between_retries=20)
        assert self.check_ue_connectivity(DAY2_SLICE_SUBSCRIBER_IMSI, retries=3, time_between_retries=20)

    def test_del_slice(self):
        assert self.context_5g.core.state.current_config.get_slice_profile(DAY2_ADDED_SLICE_ID) is not None
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_SLICE_SUBSCRIBER_IMSI) is not None

        self.nfvcl.update_blueprint(
            self.context_5g.ueransim1_bp_id,
            "ueransim/del_sim",
            UeransimBlueprintRequestDelSim(
                area_id="1",
                ue_id=1,
                imsi=DAY2_SLICE_SUBSCRIBER_IMSI,
            ),
        )
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_ues"),
            Core5GDelSubscriberModel(imsi=DAY2_SLICE_SUBSCRIBER_IMSI),
        )
        assert all(
            sim.imsi != DAY2_SLICE_SUBSCRIBER_IMSI
            for sim in self.context_5g.ueransim1.state.areas["1"].ues[0].vm_ue_configurator.sims
        )
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_SLICE_SUBSCRIBER_IMSI) is None

        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_slice"),
            Core5GDelSliceModel(sliceId=DAY2_ADDED_SLICE_ID),
        )
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_dnn"),
            Core5GDelDnnModel(dnn=DAY2_ADDED_DNN),
        )
        self._wait_for_reconfiguration(self.DELETE_SLICE_WAIT_SECONDS)

        area = self.context_5g.core.state.current_config.get_area(1)
        assert self.context_5g.core.state.current_config.get_slice_profile(DAY2_ADDED_SLICE_ID) is None
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_ADDED_DNN) is None
        assert all(area_slice.sliceId != DAY2_ADDED_SLICE_ID for area_slice in area.slices)
        assert self.check_ue_connectivity("001014000000001", retries=3, time_between_retries=20)

    def test_deploy_ueransim_for_add_area(self):
        self.context_5g.ueransim2_bp_id = self.nfvcl.create_blueprint("ueransim", self.context_5g.ueransim2_create_model)
        assert self.context_5g.ueransim2_bp_id
        self.context_5g.ueransim2 = self.nfvcl.blueprint_manager.get_blueprint_instance(self.context_5g.ueransim2_bp_id)
        assert self.context_5g.ueransim2
        assert len(self.context_5g.ueransim2.state.areas) == 1
        self.context_5g.ueransim2_ue_ssh = UeransimSSH(
            self.context_5g.ueransim2.state.areas[str(DAY2_ADDED_AREA_ID)].ues[0].vm_ue.access_ip
        )
        self.context_5g.ueransim2_gnb_ssh = UeransimSSH(
            self.context_5g.ueransim2.state.areas[str(DAY2_ADDED_AREA_ID)].vm_gnb.access_ip
        )

    def test_add_area(self):
        assert self.context_5g.core.state.current_config.get_slice_profile(DAY2_AREA_SLICE_ID) is None
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_AREA_DNN) is None
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("add_dnn"),
            _area_dnn_model(),
        )
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("add_slice_operator"),
            _area_slice_model(),
        )

        area_gnb_pdu = self._get_ueransim_gnb_pdu(DAY2_ADDED_AREA_ID)
        add_area_model = Core5GAddTacModel.model_validate(
            {
                "id": DAY2_ADDED_AREA_ID,
                "nci": "0x0",
                "idLength": 32,
                "core": False,
                "networks": {
                    "n3": self.context_5g.core_5g_create_model.areas[0].networks.n3.net_name,
                    "n6": self.context_5g.core_5g_create_model.areas[0].networks.n6.net_name,
                    "gnb": self.context_5g.core_5g_create_model.areas[0].networks.gnb.net_name
                },
                "gnb": {
                    "configure": True,
                    "pduList": [
                        area_gnb_pdu.name
                    ]
                },
                "slices": [
                    {
                        "sliceType": "EMBB",
                        "sliceId": DAY2_AREA_SLICE_ID
                    }
                ]
            }
        )

        self.nfvcl.update_blueprint(self.context_5g.core_bp_id, self._day2_path("add_tac"), add_area_model)
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("add_ues"),
            _subscriber_model(DAY2_AREA_SUBSCRIBER_IMSI, DAY2_AREA_SLICE_ID),
        )

        added_area = self.context_5g.core.state.current_config.get_area(DAY2_ADDED_AREA_ID)
        added_slice = self.context_5g.core.state.current_config.get_slice_profile(DAY2_AREA_SLICE_ID)
        self._wait_for_reconfiguration(self.ADD_AREA_WAIT_SECONDS)
        assert added_area is not None
        assert added_area.gnb is not None
        assert added_area.gnb.pduList == [area_gnb_pdu.name]
        assert added_slice is not None
        assert added_slice.dnnList == [DAY2_AREA_DNN]
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_AREA_DNN) is not None
        assert any(area_slice.sliceId == DAY2_AREA_SLICE_ID for area_slice in added_area.slices)
        assert str(DAY2_ADDED_AREA_ID) in self.context_5g.core.state.edge_areas
        assert self.context_5g.ueransim2_gnb_ssh.check_gnb_connection()
        assert self._check_ueransim2_ue_connectivity(retries=3, time_between_retries=20)
        assert self.check_ue_connectivity("001014000000001", retries=3, time_between_retries=20)

    def test_del_area(self):
        assert self.context_5g.core.state.current_config.get_area(DAY2_ADDED_AREA_ID) is not None

        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_tac"),
            Core5GDelTacModel(areaId=DAY2_ADDED_AREA_ID),
        )

        self._wait_for_reconfiguration(self.DELETE_AREA_WAIT_SECONDS)

        assert self.context_5g.core.state.current_config.get_area(DAY2_ADDED_AREA_ID) is None
        assert str(DAY2_ADDED_AREA_ID) not in self.context_5g.core.state.edge_areas
        assert str(DAY2_ADDED_AREA_ID) not in self.context_5g.core.state.ran_areas
        assert not self._check_ueransim2_ue_connectivity()
        assert self.check_ue_connectivity("001014000000001", retries=3, time_between_retries=20)

        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_ues"),
            Core5GDelSubscriberModel(imsi=DAY2_AREA_SUBSCRIBER_IMSI),
        )
        assert self.context_5g.core.state.current_config.get_subscriber(DAY2_AREA_SUBSCRIBER_IMSI) is None
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_slice"),
            Core5GDelSliceModel(sliceId=DAY2_AREA_SLICE_ID),
        )
        self.nfvcl.update_blueprint(
            self.context_5g.core_bp_id,
            self._day2_path("del_dnn"),
            Core5GDelDnnModel(dnn=DAY2_AREA_DNN),
        )
        assert self.context_5g.core.state.current_config.get_slice_profile(DAY2_AREA_SLICE_ID) is None
        assert self.context_5g.core.state.current_config.get_dnn(DAY2_AREA_DNN) is None

    def _get_ueransim_gnb_pdu(self, area_id: int):
        matching_pdus = [
            pdu
            for pdu in self.nfvcl.get_pdus()
            if pdu.area == area_id and pdu.type == PduType.GNB and pdu.instance_type == "UERANSIM"
        ]
        assert len(matching_pdus) == 1
        return matching_pdus[0]

    def _check_ueransim2_ue_connectivity(
        self,
        retries: int = 1,
        time_between_retries: int = 1,
    ) -> bool:
        ue_registered = False
        for _ in range(0, retries):
            self.context_5g.ueransim2_ue_ssh.restart_ue_service(DAY2_AREA_SUBSCRIBER_IMSI)

            ue_registered = self.context_5g.ueransim2_ue_ssh.check_ue_registered(DAY2_AREA_SUBSCRIBER_IMSI)
            if ue_registered:
                break
            time.sleep(time_between_retries)

        if not ue_registered:
            return False

        return self.context_5g.ueransim2_ue_ssh.check_ue_connectivity(DAY2_AREA_SUBSCRIBER_IMSI, "1.1.1.1")


#@pytest.mark.dependency(depends=["test_topology", "test_k8s", "test_ueransim"], scope="session")
#class TestGroup5GSDCore(Generic5GCoreTestSuite):
#    CORE_TYPE = "sdcore"
#    ADD_SUBSCRIBER_WAIT_SECONDS = 0
#    DELETE_SUBSCRIBER_WAIT_SECONDS = 0
#    ADD_SLICE_WAIT_SECONDS = 0
#    DELETE_SLICE_WAIT_SECONDS = 0
#    ADD_AREA_WAIT_SECONDS = 0
#    DELETE_AREA_WAIT_SECONDS = 0


# @pytest.mark.dependency(depends=["test_topology", "test_k8s", "test_ueransim"], scope="session")
# class TestGroup5GOAI(Generic5GCoreTestSuite):
#     CORE_TYPE = "oai"
#
#
#@pytest.mark.dependency(depends=["test_topology", "test_k8s", "test_ueransim"], scope="session")
#class TestGroup5GFree5GC(Generic5GCoreTestSuite):
#    CORE_TYPE = "free5gc"

@pytest.mark.dependency(depends=["test_topology", "test_k8s", "test_ueransim"], scope="session")
class TestGroup5GOpen5GS(Generic5GCoreTestSuite):
    CORE_TYPE = "open5gs"
