from pydantic import Field

from nfvcl_core.blueprints.ansible_builder import AnsiblePlaybookBuilder
from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure
from nfvcl_core_models.resources import PDUResourceAnsibleConfiguration
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl_core.utils.blue_utils import rel_path


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


class LiteonAIOAnsibleConfigurator(PDUResourceAnsibleConfiguration):
    vars: LiteonConfigVars
    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook LiteonAIOAnsibleConfigurator", connection="ansible.netcommon.network_cli")
        ansible_builder.set_var("ansible_network_os", "s2n_cnit.nfvcl.liteon")
        ansible_builder.add_tasks_from_file(rel_path("liteon_playbook.yaml"))
        ansible_builder.set_vars_from_fields(self.vars)
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
