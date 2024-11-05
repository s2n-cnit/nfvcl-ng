import unittest
from typing import List, Optional

from pydantic import Field

from nfvcl.blueprints_ng.lcm.blueprint_manager import BlueprintManager
from nfvcl.blueprints_ng.modules import UeransimBlueprintNG
from nfvcl.blueprints_ng.resources import VmResource
from nfvcl.blueprints_ng.utils import get_yaml_parser
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance, UeransimBlueprintRequestConfigureGNB
from nfvcl.models.blueprint_ng.worker_message import WorkerMessageType
from tests.models.config_unitest import ConfigUniteTest
from tests.models.gnb_config import GNBConfig
from tests.models.ue_config import UEConfig
from tests.utils import SSH


class UeransimGNB(NFVCLBaseModel):
    gnb: Optional[VmResource] = Field(default=None)
    ue: Optional[List[VmResource]] = Field(default_factory=list)


class UeransimTunInterface(NFVCLBaseModel):
    imsi: str = Field("")
    interface_name: str = Field("")
    ip: str = Field("")


parser = get_yaml_parser()
with open("config_unitest_dev.yaml", 'r') as stream:
    data_loaded = parser.load(stream)
    model = ConfigUniteTest.model_validate(data_loaded)

create_model: UeransimBlueprintRequestInstance = UeransimBlueprintRequestInstance.model_validate(
    {
        "config": {
            "network_endpoints": {
                "mgt": f"{model.config.networks.mgmt}",
                "n2": f"{model.config.networks.data}",
                "n3": f"{model.config.networks.data}"
            }
        },
        "areas": [
            {
                "id": 0,
                "nci": "0x00000005",
                "idLength": 0,
                "ues": [
                    {
                        "id": 1,
                        "sims": [
                            {
                                "imsi": "001014000000002",
                                "plmn": "00101",
                                "key": "814BCB2AEBDA557AEEF021BB21BEFE25",
                                "op": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                                "opType": "OPC",
                                "amf": "8000",
                                "configured_nssai": [
                                    {
                                        "sst": 1,
                                        "sd": 1
                                    }
                                ],
                                "default_nssai": [
                                    {
                                        "sst": 1,
                                        "sd": 1
                                    }
                                ],
                                "sessions": [
                                    {
                                        "type": "IPv4",
                                        "apn": "dnn",
                                        "slice": {
                                            "sst": 1,
                                            "sd": 1
                                        }
                                    }
                                ]
                            }
                        ],
                        "vim_gnbs_ips": []
                    }
                ],
                "gnb_interface_list": []
            }
        ]
    }
)

gnb_configuration = UeransimBlueprintRequestConfigureGNB.model_validate(
    {
        "area": create_model.areas[0].id,
        "plmn": "00101",
        "tac": create_model.areas[0].id,
        "amf_ip": "10.180.0.26",
        "amf_port": 8000,
        "nssai": [
            {
                "sst": 1,
                "sd": 1
            }
        ]
    }
)


def get_ueransim_tun_interface(ueransim: UeransimBlueprintNG) -> List[UeransimTunInterface]:
    interfaces: List[UeransimTunInterface] = []
    for area in ueransim.state.areas.keys():
        for ue in ueransim.state.areas[area].ues:
            connection = SSH(ue.vm_ue.access_ip)
            for sim in ue.vm_ue_configurator.sims:
                interface = connection.get_ue_TUN_name(sim.imsi)
                if interface:
                    interfaces.append(UeransimTunInterface(imsi=sim.imsi, interface_name=interface, ip=ue.vm_ue.access_ip))
            connection.close_connection()
    return interfaces


def get_gnb_ips(ueransim: UeransimBlueprintNG) -> List[str]:
    ips: List[str] = []
    for area in ueransim.state.areas.keys():
        ips.append(ueransim.state.areas[area].vm_gnb.access_ip)
    return ips


class UeransimTestCase(unittest.TestCase):
    bp_id: str
    blueprint_manager = BlueprintManager()
    blueprint: UeransimBlueprintNG
    radio_list: List[UeransimGNB] = []

    def test_001(self):
        """
        Check successful creation
        Returns:

        """

        self.__class__.bp_id = self.blueprint_manager.create_blueprint(create_model, "ueransim", True)
        self.assertIsNotNone(self.__class__.bp_id)
        self.__class__.blueprint = self.blueprint_manager.get_blueprint_instance_by_id(self.__class__.bp_id)
        print("Ended Test_001")

    def test_002_(self):
        """
        Check number of machine created
        Returns:

        """
        number_devices_created = 0
        for area in self.__class__.blueprint.state.areas.keys():
            radio: UeransimGNB = UeransimGNB()
            radio.gnb = self.__class__.blueprint.state.areas[area].vm_gnb
            number_devices_created += 1
            for ue in self.__class__.blueprint.state.areas[area].ues:
                radio.ue.append(ue.vm_ue)
                number_devices_created += 1
            self.__class__.radio_list.append(radio)

        expected_devices = len(create_model.areas)
        for area in create_model.areas:
            expected_devices += len(area.ues)

        self.assertEqual(expected_devices, number_devices_created)
        print("Ended Test_002")

    def test_003(self):
        """
        Returns:

        """
        worker = self.blueprint_manager.get_worker(self.__class__.bp_id)
        gnb_path = "/opt/UERANSIM/gnb.conf"
        for radio in self.__class__.radio_list:
            gnb_connection = SSH(radio.gnb.access_ip)
            worker.put_message_sync(WorkerMessageType.DAY2, "ueransim/configure_gnb", UeransimBlueprintRequestConfigureGNB.model_validate(gnb_configuration))
            file = gnb_connection.get_file_content(gnb_path)
            gnb_conf = GNBConfig.model_validate(parser.load(file))
            self.assertEqual(gnb_conf.tac, 0)
            self.assertEqual(gnb_conf.mcc, "001")
            self.assertEqual(gnb_conf.mnc, "01")
            self.assertEqual(gnb_conf.amf_configs[0].address, "10.180.0.26")
            self.assertEqual(gnb_conf.slices[0].sst, 1)
            self.assertEqual(gnb_conf.slices[0].sd, 1)
            self.assertNotEqual(gnb_conf.slices[0].sst, 2)
            gnb_connection.close_connection()
            for dev in radio.ue:
                ue_connection = SSH(dev.access_ip)
                for ue in create_model.areas[dev.area].ues:
                    for sim in ue.sims:
                        file = ue_connection.get_file_content(f"/opt/UERANSIM/ue-sim-{sim.imsi}.conf")
                        ue_config = UEConfig.model_validate(parser.load(file))
                        self.assertEqual(ue_config.mcc, "001")
                        self.assertEqual(ue_config.mnc, "01")
                        self.assertEqual(ue_config.supi, f"imsi-{sim.imsi}")
                        self.assertEqual(ue_config.amf, "8000")
                        self.assertEqual(ue_config.sessions[0].slice.sst, 1)
                        self.assertEqual(ue_config.sessions[0].slice.sd, 1)
                        self.assertNotEqual(ue_config.sessions[0].slice.sst, 2)
                ue_connection.close_connection()
        print("Ended Test_003")

    def test_004(self):
        """
        Check successful deletion
        Returns:

        """
        deleted_id = self.blueprint_manager.delete_blueprint(self.bp_id, True)
        self.assertIsNotNone(deleted_id)
        self.assertEqual(deleted_id, self.bp_id)
        print("Ended Test_004")
