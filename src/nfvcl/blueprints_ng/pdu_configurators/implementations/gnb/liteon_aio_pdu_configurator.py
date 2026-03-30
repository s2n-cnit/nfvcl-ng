from pydantic import Field

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure, GNBPDUDetach, GNBPDURic
from nfvcl_core_models.resources import PDUResourceAnsibleConfiguration
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.ansible_utils import run_ansible_playbook
from nfvcl_common.utils.blue_utils import rel_path


class LiteonConfigVars(NFVCLBaseModel):
    gnbid: str = Field()
    tac: str = Field()
    mcc: str = Field()
    mnc: str = Field()
    nci: str = Field()
    pci: str = Field()
    sst: str = Field()
    sd: str = Field()
    amf_ip: str = Field()
    upf_ip: str = Field()
    frequency: str = Field()


class LiteonRicVars(NFVCLBaseModel):
    remote_ip: str = Field()
    remote_port: int = Field()


class LiteonAIOAnsibleConfigurator(PDUResourceAnsibleConfiguration):
    vars: LiteonConfigVars

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LiteonAIOAnsibleConfigurator", connection="ansible.netcommon.network_cli")
        ansible_builder.set_var("ansible_network_os", "s2n_cnit.nfvcl.liteon")
        ansible_builder.add_tasks_from_file(rel_path("liteon_playbook.yaml"))
        ansible_builder.set_vars_from_fields(self.vars)
        return ansible_builder.build()


class LiteonAIODetachAnsibleConfigurator(PDUResourceAnsibleConfiguration):
    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LiteonAIOAnsibleConfigurator", connection="ansible.netcommon.network_cli")
        ansible_builder.set_var("ansible_network_os", "s2n_cnit.nfvcl.liteon")
        ansible_builder.add_tasks_from_file(rel_path("liteon_detach_playbook.yaml"))
        return ansible_builder.build()


class LiteonAIORICConfigurator(PDUResourceAnsibleConfiguration):
    vars: LiteonRicVars

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LiteonAIORICConfigurator", connection="ansible.netcommon.network_cli")
        ansible_builder.set_var("ansible_network_os", "s2n_cnit.nfvcl.liteon")
        ansible_builder.add_tasks_from_file(rel_path("liteon_ric_playbook.yaml"))
        ansible_builder.set_vars_from_fields(self.vars)
        return ansible_builder.build()


class LiteonAIOConfigReader(PDUResourceAnsibleConfiguration):

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LiteonAIOConfigReader", connection="ansible.netcommon.network_cli")
        ansible_builder.set_var("ansible_network_os", "s2n_cnit.nfvcl.liteon")
        ansible_builder.add_tasks_from_file(rel_path("liteon_config_playbook.yaml"))
        return ansible_builder.build()


class LiteonAIOPDUConfigurator(GNBPDUConfigurator):
    def configure(self, config: GNBPDUConfigure):
        if len(config.nssai) > 1:
            raise Exception("LiteON AIO gNB support only one slice")

        liteon_config_vars: LiteonConfigVars = LiteonConfigVars(
            gnbid=str(config.tac),
            tac=str(config.tac),
            mcc=config.plmn[:3],
            mnc=config.plmn[3:],
            nci=str(config.tac),
            pci=str(config.tac),
            sst=str(config.nssai[0].sst),
            sd=config.nssai[0].sd,
            amf_ip=config.amf_ip,
            upf_ip=config.upf_ip,
            frequency=self.pdu_model.config["frequency"]
        )

        run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=LiteonAIOAnsibleConfigurator(vars=liteon_config_vars).dump_playbook()
        )

    def detach(self, config: GNBPDUDetach):
        run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=LiteonAIODetachAnsibleConfigurator().dump_playbook()
        )

    def configure_ric(self, config: GNBPDURic):
        liteon_ric_vars: LiteonRicVars = LiteonRicVars(
            remote_ip=config.remote_ip,
            remote_port=config.remote_port
        )

        run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=LiteonAIORICConfigurator(vars=liteon_ric_vars).dump_playbook()
        )

    def get_gnb_id(self) -> str:
        _, fact_cache = run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=LiteonAIOConfigReader().dump_playbook()
        )
        if fact_cache.get("mcc_mnc") and fact_cache.get("gnbid"):
            mcc_mnc = fact_cache.get("mcc_mnc")
            gnbid = fact_cache.get("gnbid")
            result = {}
            for line in mcc_mnc.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    result[key.strip()] = value.strip()

            mcc = result.get("MCC").zfill(3) if result.get("MCC") and len(result.get("MCC")) != 3 else result.get("MCC")
            mnc = result.get("MNC").zfill(3) if result.get("MNC") and len(result.get("MNC")) != 3 else result.get("MNC")
            formatted_gnbid = hex(int(gnbid.split(":")[1]))[2:].zfill(7)
            return f"gnb_{mcc}_{mnc}_{formatted_gnbid}"
        else:
            raise Exception("Unable to get gnb_id")
