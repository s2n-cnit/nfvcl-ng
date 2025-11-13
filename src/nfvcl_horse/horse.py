from typing import Annotated

from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.nfvcl_public_utils import NFVCLPublic
from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.ansible_utils import run_ansible_playbook
from nfvcl_core.plugins.plugin import NFVCLPlugin
from nfvcl_core_models.resources import VmResource


class AnsibleRestAnswer(NFVCLBaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202 # OK


class NFVCLHorsePlugin(NFVCLPlugin):
    def __init__(self, nfvcl_context: NFVCL):
        super().__init__(nfvcl_context, "HorsePlugin")

    def load(self):
        print(f"Loading {self.name}")

    @NFVCLPublic(path="/ansible/run_playbook", section=NFVCL.UTILS_SECTION, method=HttpRequestType.POST)
    def run_ansible_playbook(self, host: str, username: str, password: str, payload: Annotated[str, "application/yaml"], callback=None) -> AnsibleRestAnswer:
        from nfvcl_common.ansible_utils import run_ansible_playbook
        self.nfvcl_context.add_task(run_ansible_playbook, host, username, password, payload, callback=callback)
        return AnsibleRestAnswer()


    def rtr_request(self, target: str, service: str, actionType: str, actionID: str, payload: str):
        """
        Integration for NEPHELE Project. Allow applying mitigation action on a target managed by the NFVCL (ePEM).
        Allows running an ansible playbook on a remote host. The host NEEDS to be managed by nfvcl.

        Args:

            target: The host on witch the playbook is applied ('host:port' format)

            payload: The ansible playbook in yaml format to be applied on the remote target
        """
        target_ip = target.split(":")[0]
        vm: VmResource = self.nfvcl_context.blueprint_manager.get_vm_target_by_ip(target_ip)
        if vm is None:
            # TODO post to DOC module
            return AnsibleRestAnswer(description="The Target has not been found in VMs managed by the NFVCL, the request will be forwarded to DOC module.", status="forwarded", status_code=404)
        else:
            ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, vm.username, vm.password, payload)
            if ansible_runner_result.status == "failed":
                raise Exception("Execution of Playbook failed. See NFVCL DEBUG log for more info.")
            return AnsibleRestAnswer(description="Playbook applied", status="success")

    @NFVCLPublic(path="/ansible/rtr_request", section=NFVCL.UTILS_SECTION, method=HttpRequestType.POST, sync=True, doc_by=rtr_request)
    def run_playbook(self, target: str, service: str, actionType: str, actionID: str, payload: Annotated[str, "application/yaml"], callback=None) -> AnsibleRestAnswer:
        return self.nfvcl_context.add_task(self.rtr_request, target, service, actionType, actionID, payload, callback=callback)
