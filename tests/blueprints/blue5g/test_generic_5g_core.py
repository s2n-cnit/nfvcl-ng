import time

import pytest

from blueprints.blue5g.parent5g_test import NFVCL5GTestSuite
from blueprints.ueransim_utils import UeransimSSH
from nfvcl_models.blueprint_ng.g5.core import Core5GAddSubscriberModel


@pytest.mark.dependency(depends=["test_topology", "test_k8s", "test_ueransim"], scope="session")
class TestGroup5G(NFVCL5GTestSuite):
    def test_check_ueransim_connection(self):
        assert len(self.context_5g.ueransim1.state.areas) == 1

        self.context_5g.ueransim_ue_ssh = UeransimSSH(self.context_5g.ueransim1.state.areas["1"].ues[0].vm_ue.access_ip)
        self.context_5g.ueransim_gnb_ssh = UeransimSSH(self.context_5g.ueransim1.state.areas["1"].vm_gnb.access_ip)
        # TODO check connection

    def test_deploy_core(self):
        self.context_5g.core_bp_id = self.nfvcl.create_blueprint("sdcore", self.context_5g.core_5g_create_model)
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

    def check_ue_connectivity(self, imsi):
        self.context_5g.ueransim_ue_ssh.restart_ue_service(imsi)

        ue_registred = self.context_5g.ueransim_ue_ssh.check_ue_registered(imsi)
        if not ue_registred:
            return False

        ret = self.context_5g.ueransim_ue_ssh.check_ue_connectivity(imsi, "1.1.1.1")
        return ret

    def test_check_ue_connectivity(self):
        assert self.check_ue_connectivity("001014000000001")

    def test_add_subscriber(self):
        assert len(self.context_5g.core.state.current_config.config.subscribers) == 1
        assert not self.check_ue_connectivity("001014000000002")
        new_ue: Core5GAddSubscriberModel = Core5GAddSubscriberModel.model_validate(
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
        )
        self.nfvcl.update_blueprint(self.context_5g.core_bp_id, "sdcore/add_ues", new_ue)
        assert len(self.context_5g.core.state.current_config.config.subscribers) == 2
        # TODO we need to find a way to check if the UE is registered in the core
        time.sleep(20)
        assert self.check_ue_connectivity("001014000000002")

    # def test_del_subscriber(self):
    #     pass

    # def test_add_slice(self):
    #     pass
    # def test_del_slice(self):
    #     pass
    # def test_add_tac(self):
    #     pass
    # def test_del_tac(self):
    #     pass

    # def test_delete_ueransim(self):
    #     context.ueransim_ue_ssh.close_connection()
    #     context.ueransim_gnb_ssh.close_connection()
    #     deleted_id = self.nfvcl.delete_blueprint(context.ueransim1_bp_id)
    #     assert deleted_id is not None
    #     assert deleted_id == context.ueransim1_bp_id
    #     deleted_id = self.nfvcl.delete_blueprint(context.ueransim2_bp_id)
    #     assert deleted_id is not None
    #     assert deleted_id == context.ueransim2_bp_id
    #
    # def test_delete_core(self):
    #     deleted_id = self.nfvcl.delete_blueprint(context.core_bp_id)
    #     assert deleted_id is not None
    #     assert deleted_id == context.core_bp_id
    #
# class Generic5GTestCase(unittest.TestCase):
#     bp_id: str
#     ueransim_bp_id: str
#     blueprint_manager = BlueprintManager()
#     core: SdCoreBlueprintNG
#     ueransim: UeransimBlueprintNG
#
#     def test_001_create_blueprints(self):
#         """
#         Check successful creation
#         Returns:
#
#         """
#         self.__class__.ueransim_bp_id = self.blueprint_manager.create_blueprint(ueransim_create_model, "ueransim", True)
#         self.__class__.bp_id = self.blueprint_manager.create_blueprint(create_model_5g_simple, "sdcore", True)
#         self.assertIsNotNone(self.__class__.bp_id)
#         self.__class__.core = self.blueprint_manager.get_blueprint_instance_by_id(self.__class__.bp_id)
#         self.__class__.ueransim = self.blueprint_manager.get_blueprint_instance_by_id(self.__class__.ueransim_bp_id)
#
#     # def test_002_core(self):
#     #     """
#     #     Check successful creation
#     #     Returns:
#     #
#     #     """
#     #     number_of_service = 0
#     #     services = self.__class__.core.state.core_helm_chart.services
#     #     for service in services.keys():
#     #         if "svc-lb" in service:
#     #             number_of_service += 1
#     #             ip = ''.join(services[service].external_ip[0])
#     #             self.assertTrue(check_tcp_server(ip, 80))
#     #     self.assertEqual(number_of_service, 6)
#
#     # def test_003_upf_smf(self):
#     #     """
#     #     Check upf-smf connection
#     #     Returns:
#     #
#     #     """
#     #     connection = SSH(model.config.networks.k8s_controller)
#     #     timeout = time.time() + 60 * 1
#     #     while True:
#     #         result = connection.execute_ssh_command(
#     #             f"kubectl logs -l app.kubernetes.io/name=oai-smf -n {self.__class__.bp_id.lower()} | grep 'handle_receive(16 bytes)' | wc -l")
#     #         result = result.readlines()[0].strip()
#     #         if int(result) > 0 or time.time() > timeout:
#     #             break
#     #     connection.close_connection()
#     #     self.assertTrue(int(result) > 0)
#
#     def test_004_ues(self):
#         """
#         Check if tunnel works
#         Returns:
#
#         """
#         interfaces = get_ueransim_tun_interface(self.__class__.ueransim)
#         for interface in interfaces:
#             connection = SSH(interface.ip)
#             timeout = time.time() + 60 * 1
#             while True:
#                 stdout = connection.execute_ssh_command(
#                     f"ping -c 1 -I {interface.interface_name} 1.1.1.1 > /dev/null ;  echo $?")
#                 output = stdout.readline().strip()
#                 if output == "0" or time.time() > timeout:
#                     self.assertEqual(output, "0")
#                     break
#             connection.close_connection()
#
#     def test_005_gnbs(self):
#         """
#         Check successful gnb connection to AMF
#         Returns:
#
#         """
#         gnbs_ips = get_gnb_ips(self.__class__.ueransim)
#         for ip in gnbs_ips:
#             connection = SSH(ip)
#             result = connection.check_gnb_connection()
#             connection.close_connection()
#             self.assertEqual(result.lower(), "successful")
#
#     # def test_006_add_slice(self):
#     #     self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 2)
#     #     new_slice: Core5GAddSliceModel = Core5GAddSliceModel.model_validate(
#     #         {
#     #             "sliceId": "000003",
#     #             "sliceType": "EMBB",
#     #             "dnnList": ["dnn"],
#     #             "profileParams": {
#     #                 "isolationLevel": "ISOLATION",
#     #                 "sliceAmbr": "1000Mbps",
#     #                 "ueAmbr": "50Mbps",
#     #                 "maximumNumberUE": 10,
#     #                 "pduSessions": [
#     #                     {
#     #                         "pduSessionId": "1",
#     #                         "pduSessionAmbr": "20 Mbps",
#     #                         "flows": [{
#     #                             "flowId": "1",
#     #                             "ipAddrFilter": "8.8.4.4",
#     #                             "qi": "9",
#     #                             "gfbr": "10 Mbps"
#     #                         }]
#     #                     }
#     #                 ]
#     #             },
#     #             "locationConstraints": [
#     #                 {
#     #                     "geographicalAreaId": "1",
#     #                     "tai": "00101000001"
#     #                 }
#     #             ],
#     #             "enabledUEList": [
#     #                 {
#     #                     "ICCID": "*"
#     #                 }
#     #             ],
#     #             "area_ids": [
#     #                 "0"
#     #             ]
#     #         }
#     #     )
#     #     self.core.day2_add_slice_oss(new_slice)
#     #     self.assertIsNotNone(self.core.get_slice("000003"))
#     #     self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 3)
#     #
#     # def test_007_add_subscriber(self):
#     #     """
#     #     Add subscriber
#     #     Returns:
#     #
#     #     """
#     #     self.assertEqual(len(self.core.state.current_config.config.subscribers), 1)
#     #     new_ue: Core5GAddSubscriberModel = Core5GAddSubscriberModel.model_validate(
#     #         {
#     #             "imsi": "001014000000003",
#     #             "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
#     #             "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
#     #             "snssai": [
#     #                 {
#     #                     "sliceId": "000003",
#     #                     "sliceType": "EMBB",
#     #                     "pduSessionIds": [
#     #                         "1"
#     #                     ],
#     #                     "default_slice": True
#     #                 }
#     #             ],
#     #             "authenticationMethod": "5G_AKA",
#     #             "authenticationManagementField": "8000"
#     #         }
#     #     )
#     #     self.core.day2_add_ues(new_ue)
#     #     self.assertIsNotNone(self.core.get_subscriber("001014000000003"))
#     #     self.assertNotEqual(len(self.core.state.current_config.config.subscribers), 1)
#     #     self.assertEqual(len(self.core.state.current_config.config.subscribers), 2)
#     #
#     # def test_008_ues(self):
#     #     """
#     #     Check if new tunnel works
#     #     Returns:
#     #
#     #     """
#     #     interfaces = get_ueransim_tun_interface(self.__class__.ueransim)
#     #     for interface in interfaces:
#     #         connection = SSH(interface.ip)
#     #         timeout = time.time() + 60 * 1
#     #         while True:
#     #             stdout = connection.execute_ssh_command(
#     #                 f"ping -c 1 -I {interface.interface_name} 1.1.1.1 > /dev/null ;  echo $?")
#     #             output = stdout.readline().strip()
#     #             if output == "0" or time.time() > timeout:
#     #                 self.assertEqual(output, "0")
#     #                 break
#     #         connection.close_connection()
#     #
#     # def test_009_delete_subscriber(self):
#     #     """
#     #     Delete subscriber
#     #     Returns:
#     #
#     #     """
#     #     self.assertEqual(len(self.core.state.current_config.config.subscribers), 2)
#     #     del_ue: Core5GDelSubscriberModel = Core5GDelSubscriberModel(imsi="001014000000003")
#     #     self.core.day2_del_ues(del_ue)
#     #     self.assertNotEqual(len(self.core.state.current_config.config.subscribers), 2)
#     #     self.assertEqual(len(self.core.state.current_config.config.subscribers), 1)
#     #
#     # def test_010_del_slice(self):
#     #     self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 3)
#     #     self.assertIsNotNone(self.core.get_slice("000003"))
#     #     del_slice: Core5GDelSliceModel = Core5GDelSliceModel(sliceId="000003")
#     #     self.core.day2_del_slice(del_slice)
#     #     self.assertEqual(len(self.core.state.current_config.config.sliceProfiles), 2)
#
#     def test_010_delete_bp(self):
#         """
#         Check successful deletion
#         Returns:
#
#         """
#         deleted_id = self.blueprint_manager.delete_blueprint(self.bp_id, True)
#         self.assertIsNotNone(deleted_id)
#         self.assertEqual(deleted_id, self.bp_id)
#         self.blueprint_manager.delete_blueprint(self.__class__.ueransim_bp_id, True)
#         print("Ended Test_015")
