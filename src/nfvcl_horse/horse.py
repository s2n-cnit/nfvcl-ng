import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import httpx
import yaml
from fastapi import HTTPException, Body, Query
from nfvcl_core.utils.file_utils import create_tmp_file

from nfvcl_core.utils.util import IP_PATTERN, PORT_PATTERN, IP_PORT_PATTERN, PATH_PATTERN
from pydantic import HttpUrl
from starlette import status

from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core.nfvcl_main import NFVCLPublic, NFVCLPublicMethod
from nfvcl_core.plugins.plugin import NFVCLPlugin
from nfvcl_core.providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl_core.utils.log import create_logger
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.resources import VmResource
from nfvcl_horse.models.horse_models import RTRActionType, DOCActionDNSLimit, DOCActionDNSstatus, CallbackCode, \
    RTRRestAnswer, CallbackModel, DOCNorthModel, DOCActionDefinition, DocModuleInfo

HORSE_DEFAULT_TIMEOUT = 60
HORSE_ERROR_TIMEOUT = 90
TIMEOUT = HORSE_ERROR_TIMEOUT

DUMP_FOLDER = '/tmp/ePEM/received_playbooks/'
Path(DUMP_FOLDER).mkdir(parents=True, exist_ok=True)


class AnsibleRestAnswer(NFVCLBaseModel):
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202  # OK


def extract_action(actionType: RTRActionType, playbook: str) -> DOCActionDNSLimit | DOCActionDNSstatus:
    """
    Extract action, to be used in DOC request, from playbook
    Args:
        actionType: The action type identifies the type of playbook that was received to be able to retrieve the correct data.
        playbook: The content of the playbook.

    Returns:
        The action to be included in the request body to DOC
    """
    data = yaml.safe_load(playbook)
    match actionType:
        case RTRActionType.DNS_RATE_LIMIT:
            try:
                for task in data[0]['tasks']:
                    if 'iptables' in task:
                        limit = task['iptables']['limit']
                        action = DOCActionDNSLimit(Zone="0.0.0.0", Rate=limit)
                        return action
                # If reach this point, 'iptables' was not found.
            except TypeError as error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Cannot parse tasks in the playbook: {error}")
            raise HTTPException(status_code=422, detail=f"Field >iptables< not present in the body of the playbook. Cannot parse data for DOC")
        case RTRActionType.DNS_SERV_DISABLE:
            return DOCActionDNSstatus(Zone="", Status='disabled')
        case RTRActionType.DNS_SERV_ENABLE:
            return DOCActionDNSstatus(Zone="", Status='enabled')
        case RTRActionType.TEST:
            return DOCActionDNSstatus(Zone="TEST", Status='TEST')
        case _:
            raise HTTPException(status_code=422, detail=f"Action type {actionType} not supported. Cannot parse data for DOC")


class NFVCLHorsePlugin(NFVCLPlugin):
    logger: logging.Logger

    def __init__(self, nfvcl_context: NFVCL):
        super().__init__(nfvcl_context, "HorsePlugin")
        self.logger = create_logger("Horse REST")

    def load(self):
        print(f"Loading {self.name}")

    def dump_playbook(self, playbook: str):
        """
        Dump playbook to file to debug app
        """
        now = datetime.now()
        formatted_date = now.strftime("%Y-%m-%d_%H-%M-%S")
        dump_file_name = f"{formatted_date}_{str(uuid.uuid4())}.yml"
        dump_file_dest = create_tmp_file(dump_file_name)

        try:
            dump_file_dest.write_text(playbook)
            self.logger.info("Received playbook dumped successfully.")
        except IOError as e:
            self.logger.error(f"An error while dumping received playbook: {e}")

    def build_request_for_doc(self, actionid: str, target: str, actiontype: RTRActionType, service: str, playbook) -> DOCNorthModel:
        """
        Build the request body for the DOC
        Args:
            actionid: The id of the action
            target: The IP of the target
            actiontype: The action type
            service: The service affected by mitigation
            playbook: The content of the playbook for that mitigation

        Returns:
            The filled model to be used when requesting to DOC.
        """
        action_model = extract_action(actionType=actiontype, playbook=playbook)
        action_definition = DOCActionDefinition(ActionType=actiontype, Service=service, Action=action_model.model_dump())
        doc_north_model = DOCNorthModel(ActionID=actionid, Target=target, ActionDefinition=action_definition)
        return doc_north_model

    def forward_request_to_doc(self, doc_request: DOCNorthModel, action_id: str, callback_http_url: HttpUrl):
        """
        Forward the request to the DOC module. It is used whan the request is not managed by ePEM, or should we say, the target is not managed by ePEM.
        Args:
            doc_request: The request to be forwarded to DOC
            action_id: the action ID to be used to identify the action that has been completed in the callback
            callback_http_url: The URL to which the response of the completed action is sent, also in error cases.

        Returns:

        """
        doc_info = self.nfvcl_context.extra_repository.find_one("doc_module")
        if doc_info is None:
            raise HTTPException(status_code=404, detail="DOC module is not configured, you should set using the appropriate API (/set_doc_ip_port)")
        doc_mod_info = DocModuleInfo.model_validate(doc_info)
        try:
            # Trying sending request to DOC
            self.logger.debug(f"Sending request to DOC: \n {doc_request.model_dump_json()}")
            doc_response = httpx.post(f"http://{doc_mod_info.url()}", data=doc_request.model_dump_json(), headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
            # Returning the code that
            if doc_response.status_code != 200:
                self.send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Error while forwarding request to DOC module.\n{doc_response.text}")
                raise HTTPException(status_code=doc_response.status_code, detail=f"DOC response code is different from 200: {doc_response.text}")
        except httpx.ReadTimeout:
            self.logger.debug(f"Connection Timeout to DOC module at http://{doc_mod_info.url()}")
            self.send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Connection Timeout to DOC module at http://{doc_mod_info.url()}")
            raise HTTPException(status_code=408, detail=f"Cannot contact DOC module at http://{doc_mod_info.url()}")
        except httpx.ConnectError:
            self.logger.debug(f"Connection Error to DOC module (refused at http://{doc_mod_info.url()})")
            self.send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Connection Error to DOC module (refused at http://{doc_mod_info.url()})")
            raise HTTPException(status_code=500, detail=f"Connection refused by DOC module at http://{doc_mod_info.url()}")

        doc_response_debug = {"url": str(doc_response.url), "Params": str(doc_response.headers), "Body": doc_response.text}
        self.logger.debug(f"DOC response\n{doc_response_debug}")
        ##### CALLBACK OK FORW TO DOC ###### TODO wait and forward the callback coming from the DOC
        self.send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_APPLIED_BY_DOC, description="Missing implementation of DOC callback, need to implement in future")
        return RTRRestAnswer(description=f"The request has been forwarded to DOC module", status="forwarded", status_code=200, data=doc_response_debug)

    def send_callback_http(self, url: HttpUrl, actionid: str, callback_code: CallbackCode, description: str):
        """
        Send an HTTP POST request to the URL defined for the callback; it is meant to be used when an action/mitigation as been completed.
        The body of the request contains actionid, code and description of the performed action
        Args:
            url: The URL where the callback is sent
            actionid: The ID of the performed action
            callback_code: The status code of the performed action
            description: The description of the performed action, describes the error in detail, if any.
        """
        if not url:
            return
        callback_data = CallbackModel(actionid=actionid, code=callback_code, description=description)
        try:
            # Trying sending a request to the callback URL
            self.logger.info(f"Sending callback to: \n {url}")
            callback_resp = httpx.post(str(url), data=callback_data.model_dump_json(), headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
            # Returning the code that
            if callback_resp.status_code != 200:
                raise HTTPException(status_code=callback_resp.status_code, detail=f"Callback response code is different from 200: {callback_resp.text}")
        except httpx.ReadTimeout:
            self.logger.debug(f"Connection Timeout for the callback at {url}")
            raise HTTPException(status_code=408, detail=f"Cannot contact for the callback at {url}")
        except httpx.ConnectError:
            self.logger.debug(f"Connection Error for the callback (refused at {url})")
            raise HTTPException(status_code=500, detail=f"Connection refused for the callback at {url}")
        self.logger.debug(f"Callback sent successfully to {str(url)}")

    @NFVCLPublic(path="/rtr_request_workaround", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.POST, sync=True)
    def rtr_request_workaround(self, target: str, action_type: RTRActionType, username: str, password: str, forward_to_doc: bool,
                               payload: str = Body(None, media_type="application/yaml"), service: str | None = None, actionID: str | None = None,
                               callback_http_url: HttpUrl | None = None) -> RTRRestAnswer:
        """
        Allows running an ansible playbook on a remote host.
        Integration for HORSE Project. Allow applying mitigation action on a target. This function is implemented as a workaround since in the first demo
        targets aren't managed by ePEM, but they're static. In this way it's possible to apply playbooks on targets, having usr and pwd.

        Args:

            target: The host on which the playbook is applied ('192.168.X.X' format)

            action_type: The type of action applied to the target

            username: str, the user that is used on the remote machine to apply the playbook

            password: str, the user that is used on the remote machine to apply the playbook

            forward_to_doc: str, if true, the request is forwarded to the DOC module, otherwise the playbook is applied by ePEM on the target.

            payload: body (yaml), The ansible playbook in YAML format to be applied on the remote target

            actionID: The ID of the action to be used to identify what was executed and for the callback

            service: The service affected by the mitigation/action, this relates to the action type and the target.

            callback_http_url: The URL to which the response of the completed action is sent, also in error cases.
        """
        self.dump_playbook(playbook=payload)
        if forward_to_doc is False:
            # No forward to DOC mean that playbook should be applied
            self.logger.debug("Started applying ansible playbook")
            ansible_runner_result, fact_cache = run_ansible_playbook(target, username, password, payload)
            if ansible_runner_result.status == "failed":
                self.send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_EPEM, description="Execution of Playbook failed. See ePEM DEBUG log for more info (http://ePEM_IP:5002/logs).")
                raise HTTPException(status_code=500, detail="Execution of Playbook failed. See ePEM DEBUG log for more info (http://ePEM_IP:5002/logs).")
            msg_return = RTRRestAnswer(description="Playbook applied", status="success")
            self.logger.debug(msg_return)
            ##### CALLBACK OK ######
            self.send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_APPLIED_BY_EPEM, description="Action applied by the ePEM")
            return msg_return
        else:
            # Request should be forwarded to DOC
            if actionID is None:
                actionID = str(uuid.uuid4())
            if service is None:
                service = "DNS"  # TODO Workaround
            body: DOCNorthModel = self.build_request_for_doc(actionid=actionID, target=target, actiontype=action_type, service=service, playbook=payload)
            msg_return = self.forward_request_to_doc(body, actionID, callback_http_url)
            return msg_return

    #@horse_router.post("/rtr_request", response_model=RTRRestAnswer)
    @NFVCLPublic(path="/rtr_request", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.POST, sync=True)
    def rtr_request(self, target_ip: Annotated[str, Query(pattern=IP_PATTERN)], target_port: Optional[Annotated[str, Query(pattern=PORT_PATTERN)]],
                    service: str, actionType: RTRActionType, actionID: str, payload: str = Body(None, media_type="application/yaml"),
                    callback_http_url: HttpUrl | None = None) -> RTRRestAnswer:
        """
        Integration for HORSE Project. Allow applying mitigation action on a target managed by the NFVCL (ePEM).
        Allows running an ansible playbook on a remote host. The host NEEDS to be managed by nfvcl.

        See Also:

            [HORSE_Demo3_Components_Specification_v0.1](https://tntlabunigeit-my.sharepoint.com/:w:/r/personal/horse-cloud_tnt-lab_unige_it/_layouts/15/Doc.aspx?sourcedoc=%7B34097F2D-C0F8-4E06-B34C-0BA0B3D81DE0%7D&file=HORSE_Demo3_Components_Specification_v0.1.docx&action=default&mobileredirect=true)

        Args:

            target_ip: The IP of the host on which the Ansible playbook is applied ('1.52.65.25' format)

            target_port: The port used by Ansible on the host in which the playbook is applied. This is OPTIONAL for future use.

            service: str, Service type for our demo 3 "DNS" should be obtained from RTR request

            actionType: str, For this first iteration is always going to be a "Service modification" but for the second iteration should be other type of actions

            actionID: str, this field should be provided by RTR, I think that is really important for the second iteration since we need to control the life cycle of actions, so we should implement it now but could be a dummy parameter for this iteration

            payload: body (yaml), The ansible playbook in yaml format to be applied on the remote target
        """
        self.dump_playbook(playbook=payload)
        # IF in DEBUG mode, the blueprint manager isn't loaded
        if not os.environ.get('HORSE_DEBUG'):
            blueprint_manager = self.nfvcl_context.blueprint_manager
            vm: VmResource | None = blueprint_manager.get_vm_target_by_ip(target_ip)
        else:
            # In DEBUG mode only local target is allowed (ePEM itself)
            if target_ip == "127.0.0.1":
                vm = "not_none"
            else:
                vm = None

        if vm is None:
            # This is the case where the VM is not managed by the ePEM -> Request is forwarded to DOC
            body: DOCNorthModel = self.build_request_for_doc(actionid=actionID, target=target_ip, actiontype=actionType, service=service, playbook=payload)
            msg_return = self.forward_request_to_doc(body, actionID, callback_http_url)
            return msg_return
        else:
            # Action applied by ePEM
            self.logger.debug("Started applying ansible playbook")
            if not os.environ.get('HORSE_DEBUG'):
                ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, vm.username, vm.password, payload)
            else:
                ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, "ubuntutest", "ubuntutest", payload)
            if ansible_runner_result.status == "failed":
                self.send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_EPEM, description="Execution of Playbook failed. See ePEM DEBUG log for more info (http://ePEM_IP:5002/logs).")
                raise HTTPException(status_code=500, detail="Execution of Playbook failed. See ePEM DEBUG log for more info (http://ePEM_IP:5002/logs).")

            msg_return = RTRRestAnswer(description="Playbook applied", status="success")
            self.send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_APPLIED_BY_EPEM, description="Action applied by the ePEM")
            self.logger.info(msg_return)
            return msg_return

    @NFVCLPublic(path="/set_doc_ip_port", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.POST, sync=True)
    def set_doc_ip_port(self, doc_ip: Annotated[str, Query(pattern=IP_PATTERN)], doc_port: Annotated[int, Query(ge=0, le=65535)], path: Annotated[str, Query(pattern=PATH_PATTERN)]) -> RTRRestAnswer:
        """
        Set up and save the URL of HORSE DOC module. The URL is composed by {doc_ip_port}{url_path}
        """
        module_info = DocModuleInfo(ipaddress=doc_ip, port=doc_port, path=path)
        self.nfvcl_context.extra_repository.save("doc_module", module_info.model_dump())
        msg_return = RTRRestAnswer(description="DOC module IP has been set", status="success")
        self.logger.info(msg_return.description)
        return msg_return

    @NFVCLPublic(path="/get_doc_ip_port", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_doc_ip_port(self) -> RTRRestAnswer:
        """
        Allows retrieving the DOC URL
        """
        doc_info = self.nfvcl_context.extra_repository.find_one("doc_module")
        if doc_info is None:
            raise HTTPException(status_code=404, detail="DOC module is not configured, you should set using the appropriate API.")
        doc_mod_info = DocModuleInfo.model_validate(doc_info)
        return RTRRestAnswer(description="DOC URL has been set", status="success", data=doc_mod_info.model_dump())
