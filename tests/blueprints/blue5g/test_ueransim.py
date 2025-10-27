import pytest
from blueprints.blue5g.day2_configs import GNB_CONFIGURATION
from blueprints.blue5g.models.ueransim import GNBConfig, UEConfig, UeransimGNB
from blueprints.blue5g.parent5g_test import NFVCL5GTestSuite
from blueprints.ueransim_utils import UeransimSSH
from nfvcl_common.utils.blue_utils import get_yaml_parser
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure


# def get_ueransim_tun_interface(ueransim: UeransimBlueprintNG) -> List[UeransimTunInterface]:
#     interfaces: List[UeransimTunInterface] = []
#     for area in ueransim.state.areas.keys():
#         for ue in ueransim.state.areas[area].ues:
#             connection = UeransimSSH(ue.vm_ue.access_ip)
#             for sim in ue.vm_ue_configurator.sims:
#                 interface = connection.get_ue_tun_name(sim.imsi)
#                 if interface:
#                     interfaces.append(UeransimTunInterface(imsi=sim.imsi, interface_name=interface, ip=ue.vm_ue.access_ip))
#             connection.close_connection()
#     return interfaces
#
#
# def get_gnb_ips(ueransim: UeransimBlueprintNG) -> List[str]:
#     ips: List[str] = []
#     for area in ueransim.state.areas.keys():
#         ips.append(ueransim.state.areas[area].vm_gnb.access_ip)
#     return ips

@pytest.mark.dependency(name="test_ueransim", depends=["test_topology"], scope="session")
class TestGroupUERANSIM(NFVCL5GTestSuite):
    def test_deployment(self):
        """
        Check successful creation
        Returns:

        """
        self.context_5g.ueransim1_bp_id = self.nfvcl.create_blueprint("ueransim", self.context_5g.ueransim1_create_model)
        assert self.context_5g.ueransim1_bp_id
        self.context_5g.ueransim1 = self.nfvcl.blueprint_manager.get_blueprint_instance(self.context_5g.ueransim1_bp_id)
        assert self.context_5g.ueransim1

    @pytest.mark.dependency()
    def test_vms_number_check(self):
        """
        Check number of machine created
        Returns:

        """
        number_devices_created = 0
        for area in self.context_5g.ueransim1.state.areas.keys():
            radio: UeransimGNB = UeransimGNB()
            radio.gnb = self.context_5g.ueransim1.state.areas[area].vm_gnb
            number_devices_created += 1
            for ue in self.context_5g.ueransim1.state.areas[area].ues:
                radio.ue.append(ue.vm_ue)
                number_devices_created += 1
            self.context_5g.ueransim1_radio_list.append(radio)

        expected_devices = len(self.context_5g.ueransim1_create_model.areas)
        for area in self.context_5g.ueransim1_create_model.areas:
            expected_devices += len(area.ues)

        assert expected_devices == number_devices_created

    @pytest.mark.dependency(depends=["test_vms_number_check"], scope="class")
    def test_check_config_files(self):
        gnb_path = "/opt/UERANSIM/gnb.conf"
        for radio in self.context_5g.ueransim1_radio_list:
            gnb_connection = UeransimSSH(radio.gnb.access_ip)
            self.nfvcl.update_blueprint(self.context_5g.ueransim1_bp_id, "ueransim/configure_gnb", GNBPDUConfigure.model_validate(GNB_CONFIGURATION))
            file = gnb_connection.get_file_content(gnb_path)
            gnb_conf = GNBConfig.model_validate(get_yaml_parser().load(file))
            assert gnb_conf.tac == 1
            assert gnb_conf.mcc == "001"
            assert gnb_conf.mnc == "01"
            assert gnb_conf.amf_configs[0].address == "10.180.0.26"
            assert gnb_conf.slices[0].sst == 1
            assert gnb_conf.slices[0].sd == 1
            gnb_connection.close_connection()
            for dev in radio.ue:
                ue_connection = UeransimSSH(dev.access_ip)
                for ue in self.context_5g.ueransim1_create_model.areas[0].ues:
                    for sim in ue.sims:
                        file = ue_connection.get_file_content(f"/opt/UERANSIM/ue-sim-{sim.imsi}.conf")
                        ue_config = UEConfig.model_validate(get_yaml_parser().load(file))
                        assert ue_config.mcc == "001"
                        assert ue_config.mnc == "01"
                        assert ue_config.supi == f"imsi-{sim.imsi}"
                        assert ue_config.amf == "8000"
                        assert ue_config.sessions[0].slice.sst == 1
                        assert ue_config.sessions[0].slice.sd == 1
                ue_connection.close_connection()
