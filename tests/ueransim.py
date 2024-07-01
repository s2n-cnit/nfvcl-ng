import unittest
from typing import List, Dict

from nfvcl.blueprints_ng.lcm.blueprint_manager import BlueprintManager
from nfvcl.blueprints_ng.utils import get_yaml_parser
from nfvcl.models.base_model import NFVCLBaseModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance, UeransimBlueprintRequestConfigureGNB
from nfvcl.models.blueprint_ng.worker_message import WorkerMessageType
from tests.models.config_unitest import Model
from tests.models.gnb_config import GNBConfig
from tests.models.ue_config import UEConfig
from tests.utils import SSH


class UeransimVM(NFVCLBaseModel):
    ip: str
    name: str
    area: int


parser = get_yaml_parser()
with open("config_unitest_dev.yaml", 'r') as stream:
    data_loaded = parser.load(stream)
    model = Model.model_validate(data_loaded)

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


class UeransimTestCase(unittest.TestCase):
    bp_id: str
    blueprint_manager = BlueprintManager()
    details: Dict = []
    device_list: List[UeransimVM] = []

    def test_001(self):
        """
        Check successful creation
        Returns:

        """

        self.__class__.bp_id = self.blueprint_manager.create_blueprint(create_model, "ueransim", True)
        self.assertIsNotNone(self.__class__.bp_id)
        self.__class__.details = self.blueprint_manager.get_blueprint_summary_by_id(self.__class__.bp_id, True)
        print("Ended Test_001")

    def test_002_(self):
        """
        Check number of machine created
        Returns:

        """
        for vm_id in self.__class__.details['registered_resources'].keys():
            vm_data = self.__class__.details['registered_resources'][vm_id]['value']
            if "access_ip" in vm_data and ("GNB" or "UE" in vm_data["name"]):
                ip = vm_data['access_ip']
                name = vm_data['name']
                area = vm_data['area']
                new_device = UeransimVM(ip=ip, name=name, area=area)
                self.__class__.device_list.append(new_device)

        expected_devices = len(create_model.areas)
        for area in create_model.areas:
            expected_devices += len(area.ues)

        self.assertEqual(expected_devices, len(self.__class__.device_list))
        print("Ended Test_002")

    def test_003(self):
        """
        Returns:

        """
        worker = self.blueprint_manager.get_worker(self.__class__.bp_id)
        gnb_path = "/opt/UERANSIM/gnb.conf"
        for device in self.__class__.device_list:
            connection = SSH(device.ip)
            if "GNB" in device.name:
                worker.put_message_sync(WorkerMessageType.DAY2, "ueransim/configure_gnb", UeransimBlueprintRequestConfigureGNB.model_validate(gnb_configuration))
                file = connection.get_file_content(gnb_path)
                gnb_conf = GNBConfig.model_validate(parser.load(file))
                self.assertEqual(gnb_conf.tac, 0)
                self.assertEqual(gnb_conf.mcc, "001")
                self.assertEqual(gnb_conf.mnc, "01")
                self.assertEqual(gnb_conf.amf_configs[0].address, "10.180.0.26")
                self.assertEqual(gnb_conf.slices[0].sst, 1)
                self.assertEqual(gnb_conf.slices[0].sd, 1)
                self.assertNotEqual(gnb_conf.slices[0].sst, 2)
            else:
                for ue in create_model.areas[device.area].ues:
                    for sim in ue.sims:
                        file = connection.get_file_content(f"/opt/UERANSIM/ue-sim-{sim.imsi}.conf")
                        ue_config = UEConfig.model_validate(parser.load(file))
                        self.assertEqual(ue_config.mcc, "001")
                        self.assertEqual(ue_config.mnc, "01")
                        self.assertEqual(ue_config.supi, f"imsi-{sim.imsi}")
                        self.assertEqual(ue_config.amf, "8000")
                        self.assertEqual(ue_config.sessions[0].slice.sst, 1)
                        self.assertEqual(ue_config.sessions[0].slice.sd, 1)
                        self.assertNotEqual(ue_config.sessions[0].slice.sst, 2)
            connection.close_connection()
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
