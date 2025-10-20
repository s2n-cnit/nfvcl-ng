from typing import List

from pydantic import Field

from nfvcl_models.blueprint_ng.g5.common5g import Slice5G
from nfvcl_core.blueprints.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUException
from nfvcl.blueprints_ng.pdu_configurators.types.gnb_pdu_configurator import GNBPDUConfigurator
from nfvcl_core_models.pdu.gnb import GNBPDUConfigure
from nfvcl_core_models.resources import PDUResourceAnsibleConfiguration
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl_core.utils.blue_utils import rel_path


class AmariPLMN(NFVCLBaseModel):
    plmn: str = Field()
    tac: int = Field()
    reserved: bool = Field() # True if the cell is reserved for operator use
    nssai: List[Slice5G] = Field(default_factory=list)

class AmariPDUConfig(NFVCLBaseModel):
    nr_tdd: int = Field(ge=0, le=1)
    nr_tdd_config: int = Field(ge=1, le=4)
    nr_bandwidth: int = Field(ge=0)

    n_antenna_dl: int = Field(ge=1, le=4)
    n_antenna_ul: int = Field(ge=1, le=4)
    use_srs: int = Field(ge=0, le=1)
    logfile: str = Field(pattern=r"^(/[^/ ]*)+/?$")

class AmariConfigVars(NFVCLBaseModel):
    gtp_ip: str = Field() # Bind IP of the AMF interface from Amari side
    amf_ip: str = Field()

    gnb_id_bits: int = Field()
    gnb_id: str = Field(pattern=r"0[xX][0-9a-fA-F]+")
    cell_id: str = Field(pattern=r"0[xX][0-9a-fA-F]+")
    n_id_cell: int = Field()

    plmn_list: List[AmariPLMN] = Field()


class AmariAnsibleConfigurator(PDUResourceAnsibleConfiguration):
    pdu_config: AmariPDUConfig
    vars: AmariConfigVars
    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook AmariAnsibleConfigurator")
        ansible_builder.add_template_task(rel_path("gnb-sa.cfg.jinja2"), "/root/enb/config/gnb_nfvcl.cfg")
        ansible_builder.add_shell_task(f"ln -sf /root/enb/config/gnb_nfvcl.cfg /root/enb/config/enb.cfg")
        ansible_builder.add_service_task("lte", ServiceState.RESTARTED)
        ansible_builder.set_vars_from_fields(self.pdu_config)
        ansible_builder.set_vars_from_fields(self.vars)
        return ansible_builder.build()


class AmariPDUConfigurator(GNBPDUConfigurator):
    def configure(self, config: GNBPDUConfigure):
        amari_config_vars: AmariConfigVars = AmariConfigVars(
            gtp_ip=self.pdu_model.get_mgmt_ip(), # TODO this is not correct in some configurations
            amf_ip=config.amf_ip,
            gnb_id_bits=32,
            gnb_id=f"{config.tac:#0{8}x}",
            cell_id=f"{config.tac:#0{8}x}",
            n_id_cell=config.tac,
            plmn_list=[AmariPLMN(plmn=config.plmn, tac=config.tac, reserved=False, nssai=config.nssai)]
        )

        amari_pdu_config = AmariPDUConfig.model_validate(self.pdu_model.config)

        ansible_runner_result, fact_cache = run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=AmariAnsibleConfigurator(vars=amari_config_vars, pdu_config=amari_pdu_config).dump_playbook()
        )

        if ansible_runner_result.status == "failed":
            raise PDUException("Error configuring Amarisoft GNB")
