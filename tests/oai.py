import time
import unittest

from nfvcl.blueprints_ng.lcm.blueprint_manager import BlueprintManager
from nfvcl.blueprints_ng.modules import OpenAirInterface, UeransimBlueprintNG
from nfvcl.blueprints_ng.utils import get_yaml_parser
from nfvcl.models.blueprint_ng.core5g.OAI_Models import OAIBlueCreateModel
from nfvcl.models.blueprint_ng.core5g.common import SubSubscribers
from nfvcl.models.blueprint_ng.g5.core import Core5GDelSubscriberModel, Core5GAddSliceModel, Core5GDelSliceModel, Core5GAddSubscriberModel
from nfvcl.models.blueprint_ng.g5.ueransim import UeransimBlueprintRequestInstance
from tests.models.config_unitest import ConfigUniteTest
from tests.utils import check_tcp_server, SSH
from ueransim import get_ueransim_tun_interface, get_gnb_ips

parser = get_yaml_parser()
with open("config_unitest_dev.yaml", 'r') as stream:
    data_loaded = parser.load(stream)
    model = ConfigUniteTest.model_validate(data_loaded)

create_model: OAIBlueCreateModel = OAIBlueCreateModel.model_validate(
    {
        "type": "OpenAirInterface",
        "config": {
            "network_endpoints": {
                "mgt": f"{model.config.networks.mgmt}",
                "wan": f"{model.config.networks.data}",
                "data_nets": [
                    {
                        "net_name": "dnn",
                        "dnn": "dnn",
                        "dns": "8.8.8.8",
                        "pools": [
                            {
                                "cidr": "12.168.0.0/16"
                            }
                        ],
                        "uplinkAmbr": "100 Mbps",
                        "downlinkAmbr": "100 Mbps",
                        "default5qi": "9"
                    }
                ]
            },
            "plmn": "00101",
            "sliceProfiles": [
                {
                    "sliceId": "000001",
                    "sliceType": "EMBB",
                    "dnnList": ["dnn"],
                    "profileParams": {
                        "isolationLevel": "ISOLATION",
                        "sliceAmbr": "1000Mbps",
                        "ueAmbr": "50Mbps",
                        "maximumNumberUE": 10,
                        "pduSessions": [
                            {
                                "pduSessionId": "1",
                                "pduSessionAmbr": "20 Mbps",
                                "flows": [{
                                    "flowId": "1",
                                    "ipAddrFilter": "8.8.4.4",
                                    "qi": "9",
                                    "gfbr": "10 Mbps"
                                }]
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
                    ]
                },
                {
                    "sliceId": "000002",
                    "sliceType": "EMBB",
                    "dnnList": ["dnn"],
                    "profileParams": {
                        "isolationLevel": "ISOLATION",
                        "sliceAmbr": "1000Mbps",
                        "ueAmbr": "50Mbps",
                        "maximumNumberUE": 10,
                        "pduSessions": [
                            {
                                "pduSessionId": "1",
                                "pduSessionAmbr": "20 Mbps",
                                "flows": [{
                                    "flowId": "1",
                                    "ipAddrFilter": "8.8.4.4",
                                    "qi": "9",
                                    "gfbr": "10 Mbps"
                                }]
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
                    ]
                }
            ],
            "subscribers": [
                {
                    "imsi": "001014000000002",
                    "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
                    "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                    "snssai": [
                        {
                            "sliceId": "000001",
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
            ]
        },
        "areas": [
            {
                "id": 0,
                "nci": "0x0",
                "idLength": 32,
                "core": True,
                "slices": [{
                    "sliceType": "EMBB",
                    "sliceId": "000001"
                }]
            }
        ]
    }
)

ueransim_create_model: UeransimBlueprintRequestInstance = UeransimBlueprintRequestInstance.model_validate(
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


class OAITestCase(unittest.TestCase):
    bp_id: str
    ueransim_bp_id: str
    blueprint_manager = BlueprintManager()
    core: OpenAirInterface = []
    ueransim: UeransimBlueprintNG

    def test_001_create_bp(self):
        """
        Check successful creation
        Returns:

        """
        self.__class__.ueransim_bp_id = self.blueprint_manager.create_blueprint(ueransim_create_model, "ueransim", True)
        self.__class__.bp_id = self.blueprint_manager.create_blueprint(create_model, "OpenAirInterface", True)
        self.assertIsNotNone(self.__class__.bp_id)
        self.__class__.core = self.blueprint_manager.get_blueprint_instance_by_id(self.__class__.bp_id)
        self.__class__.ueransim = self.blueprint_manager.get_blueprint_instance_by_id(self.__class__.ueransim_bp_id)

    def test_002_core(self):
        """
        Check successful creation
        Returns:

        """
        number_of_service = 0
        services = self.__class__.core.state.core_helm_chart.services
        for service in services.keys():
            if "svc-lb" in service:
                number_of_service += 1
                ip = ''.join(services[service].external_ip[0])
                self.assertTrue(check_tcp_server(ip, 80))
        self.assertEqual(number_of_service, 6)

    def test_003_upf_smf(self):
        """
        Check upf-smf connection
        Returns:

        """
        connection = SSH(model.config.networks.k8s_controller)
        timeout = time.time() + 60 * 1
        while True:
            result = connection.execute_ssh_command(
                f"kubectl logs -l app.kubernetes.io/name=oai-smf -n {self.__class__.bp_id.lower()} | grep 'handle_receive(16 bytes)' | wc -l")
            result = result.readlines()[0].strip()
            if int(result) > 0 or time.time() > timeout:
                break
        connection.close_connection()
        self.assertTrue(int(result) > 0)

    def test_004_ues(self):
        """
        Check if tunnel works
        Returns:

        """
        interfaces = get_ueransim_tun_interface(self.__class__.ueransim)
        for interface in interfaces:
            connection = SSH(interface.ip)
            timeout = time.time() + 60 * 1
            while True:
                stdout = connection.execute_ssh_command(
                    f"ping -c 1 -I {interface.interface_name} 1.1.1.1 > /dev/null ;  echo $?")
                output = stdout.readline().strip()
                if output == "0" or time.time() > timeout:
                    self.assertEqual(output, "0")
                    break
            connection.close_connection()

    def test_005_gnbs(self):
        """
        Check successful gnb connection to AMF
        Returns:

        """
        gnbs_ips = get_gnb_ips(self.__class__.ueransim)
        for ip in gnbs_ips:
            connection = SSH(ip)
            result = connection.check_gnb_connection()
            connection.close_connection()
            self.assertEqual(result.lower(), "successful")

    def test_006_add_slice(self):
        self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 2)
        new_slice: Core5GAddSliceModel = Core5GAddSliceModel.model_validate(
            {
                "sliceId": "000003",
                "sliceType": "EMBB",
                "dnnList": ["dnn"],
                "profileParams": {
                    "isolationLevel": "ISOLATION",
                    "sliceAmbr": "1000Mbps",
                    "ueAmbr": "50Mbps",
                    "maximumNumberUE": 10,
                    "pduSessions": [
                        {
                            "pduSessionId": "1",
                            "pduSessionAmbr": "20 Mbps",
                            "flows": [{
                                "flowId": "1",
                                "ipAddrFilter": "8.8.4.4",
                                "qi": "9",
                                "gfbr": "10 Mbps"
                            }]
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
                    "0"
                ]
            }
        )
        self.core.day2_add_slice_oss(new_slice)
        self.assertIsNotNone(self.core.get_slice("000003"))
        self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 3)

    def test_007_add_subscriber(self):
        """
        Add subscriber
        Returns:

        """
        self.assertEqual(len(self.core.state.current_config.config.subscribers), 1)
        new_ue: Core5GAddSubscriberModel = Core5GAddSubscriberModel.model_validate(
            {
                "imsi": "001014000000003",
                "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
                "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
                "snssai": [
                    {
                        "sliceId": "000003",
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
        self.core.day2_add_ues(new_ue)
        self.assertIsNotNone(self.core.get_subscriber("001014000000003"))
        self.assertNotEqual(len(self.core.state.current_config.config.subscribers), 1)
        self.assertEqual(len(self.core.state.current_config.config.subscribers), 2)

    def test_008_ues(self):
        """
        Check if new tunnel works
        Returns:

        """
        interfaces = get_ueransim_tun_interface(self.__class__.ueransim)
        for interface in interfaces:
            connection = SSH(interface.ip)
            timeout = time.time() + 60 * 1
            while True:
                stdout = connection.execute_ssh_command(
                    f"ping -c 1 -I {interface.interface_name} 1.1.1.1 > /dev/null ;  echo $?")
                output = stdout.readline().strip()
                if output == "0" or time.time() > timeout:
                    self.assertEqual(output, "0")
                    break
            connection.close_connection()

    def test_009_delete_subscriber(self):
        """
        Delete subscriber
        Returns:

        """
        self.assertEqual(len(self.core.state.current_config.config.subscribers), 2)
        del_ue: Core5GDelSubscriberModel = Core5GDelSubscriberModel(imsi="001014000000003")
        self.core.day2_del_ues(del_ue)
        self.assertNotEqual(len(self.core.state.current_config.config.subscribers), 2)
        self.assertEqual(len(self.core.state.current_config.config.subscribers), 1)

    def test_010_del_slice(self):
        self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 3)
        self.assertIsNotNone(self.core.get_slice("000003"))
        del_slice: Core5GDelSliceModel = Core5GDelSliceModel(sliceId="000003")
        self.core.day2_del_slice(del_slice)
        self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 2)

    def test_010_delete_bp(self):
        """
        Check successful deletion
        Returns:

        """
        deleted_id = self.blueprint_manager.delete_blueprint(self.bp_id, True)
        self.assertIsNotNone(deleted_id)
        self.assertEqual(deleted_id, self.bp_id)
        self.blueprint_manager.delete_blueprint(self.__class__.ueransim_bp_id, True)
        print("Ended Test_015")
