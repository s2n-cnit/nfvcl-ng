from nfvcl.blueprints_ng.pdu_configurators.pdu_configurator import PDUConfigurator
from nfvcl_common.ansible_utils import run_ansible_playbook


class GenericLinuxPDUConfigurator(PDUConfigurator):
    def run_ansible(self, playbook: str):
        run_ansible_playbook(host=self.pdu_model.get_mgmt_ip(), username=self.pdu_model.username, password=self.pdu_model.password, playbook=playbook)
