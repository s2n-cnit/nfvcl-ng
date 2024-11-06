import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
import yaml
import httpx
from fastapi import APIRouter, status, Body, Query, HTTPException
from httpx import ConnectTimeout, Response
from pydantic import HttpUrl

from nfvcl.blueprints_ng.providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl.blueprints_ng.resources import VmResource
from nfvcl.models.HORSE.horse_models import RTRRestAnswer, RTRActionType, DOCActionDNSstatus, DOCActionDNSLimit, \
    DOCActionDefinition, DOCNorthModel, CallbackCode, CallbackModel
from nfvcl.utils.database import insert_extra, get_extra
from nfvcl.utils.util import IP_PORT_PATTERN, PATH_PATTERN, IP_PATTERN, PORT_PATTERN
from nfvcl.utils.log import create_logger
import os
import logging

DEFAULT_TIMEOUT = 60
ERROR_TIMEOUT = 90


def get_timeout_from_env(logger: logging.Logger) -> int:
    timeout_str = os.environ.get('HORSE_TIMEOUT')
    if timeout_str:
        try:
            return int(timeout_str)
        except ValueError:
            logger.error("Cannot correctly read HORSE_TIMEOUT env variable, setting it to 90")
            return ERROR_TIMEOUT
    return DEFAULT_TIMEOUT


# Only import get_blueprint_manager if HORSE_DEBUG is not set
if not os.environ.get('HORSE_DEBUG'):
    from nfvcl.rest_endpoints.blue_ng_router import get_blueprint_manager

logger: logging.Logger = create_logger("Horse REST")

# Get and set the timeout value
TIMEOUT = get_timeout_from_env(logger)
logger.info(f"Horse DOC timeout set to {TIMEOUT}")
horse_router = APIRouter(
    prefix="/v2/horse",
    tags=["Horse"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


DUMP_FOLDER = '/tmp/ePEM/received_playbooks/'
Path(DUMP_FOLDER).mkdir(parents=True, exist_ok=True)


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

def dump_playbook(playbook: str):
    """
    Dump playbook to file to debug app
    """
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d_%H-%M-%S")
    dump_file_name = f"{formatted_date}_{str(uuid.uuid4())}.yml"
    dump_file_dest = Path(DUMP_FOLDER, dump_file_name)
    dump_file_dest.touch(exist_ok=True)

    try:
        dump_file_dest.write_text(playbook)
        logger.info("Received playbook dumped successfully.")
    except IOError as e:
        logger.error(f"An error while dumping received playbook: {e}")

def build_request_for_doc(actionid: str, target: str, actiontype: RTRActionType, service: str, playbook) -> DOCNorthModel:
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


def forward_request_to_doc(doc_mod_info: dict, doc_request: DOCNorthModel, action_id: str, callback_http_url: HttpUrl):
    if 'url' in doc_mod_info:
        doc_module_url = doc_mod_info['url']
        doc_response: Response
        try:
            # Trying sending request to DOC
            logger.debug(f"Sending request to DOC: \n {doc_request.model_dump_json()}")
            doc_response = httpx.post(f"http://{doc_module_url}", data=doc_request.model_dump_json(), headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
            # Returning the code that
            if doc_response.status_code != 200:
                send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Error while forwarding request to DOC module.\n{doc_response.text}")
                raise HTTPException(status_code=doc_response.status_code, detail=f"DOC response code is different from 200: {doc_response.text}")
        except httpx.ReadTimeout:
            logger.debug(f"Connection Timeout to DOC module at http://{doc_module_url}")
            send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Connection Timeout to DOC module at http://{doc_module_url}")
            raise HTTPException(status_code=408, detail=f"Cannot contact DOC module at http://{doc_module_url}")
        except httpx.ConnectError:
            logger.debug(f"Connection Error to DOC module (refused at http://{doc_module_url})")
            send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description=f"Connection Error to DOC module (refused at http://{doc_module_url})")
            raise HTTPException(status_code=500, detail=f"Connection refused by DOC module at http://{doc_module_url}")

        doc_response_debug = f"HTTP Status code: {doc_response.status_code}\nUrl: {doc_response.url}\nParams: {doc_response.headers}\nBody: {doc_response.text}"
        logger.info(f"DOC response\n{doc_response_debug}")
        ##### CALLBACK OK FORW TO DOC ###### TODO wait and forward the callback coming from the DOC
        send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_APPLIED_BY_DOC, description="Missing implementation of DOC callback, need to implement in future")
        return RTRRestAnswer(description=f"The request has been forwarded to DOC module. DOC responce is: \n {doc_response_debug}", status="forwarded", status_code=200)
    else:
        msg_return = RTRRestAnswer(description="The request has NOT been forwarded to DOC module cause there is NO DOC module info or missing URL. Please use /set_doc_ip_port to set the URL.", status="error", status_code=500)
        logger.error(msg_return.description)
        ##### CALLBACK ERROR ######
        send_callback_http(callback_http_url, action_id, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_DOC, description="The action should be forwarded to DOC but it's IP is missing.")

        return msg_return


def send_callback_http(url: HttpUrl, actionid: str, callback_code: CallbackCode, description: str):
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
        logger.info(f"Sending callback to: \n {url}")
        callback_resp = httpx.post(str(url), data=callback_data.model_dump_json(), headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
        # Returning the code that
        if callback_resp.status_code != 200:
            raise HTTPException(status_code=callback_resp.status_code, detail=f"Callback response code is different from 200: {callback_resp.text}")
    except httpx.ReadTimeout:
        logger.debug(f"Connection Timeout for the callback at {url}")
        raise HTTPException(status_code=408, detail=f"Cannot contact for the callback at {url}")
    except httpx.ConnectError:
        logger.debug(f"Connection Error for the callback (refused at {url})")
        raise HTTPException(status_code=500, detail=f"Connection refused for the callback at {url}")
    logger.debug(f"Callback sent successfully to {str(url)}")


@horse_router.post("/rtr_request_workaround", response_model=RTRRestAnswer)
def rtr_request_workaround(target: str, action_type: RTRActionType, username: str, password: str, forward_to_doc: bool,
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
    dump_playbook(playbook=payload)
    if forward_to_doc is False:
        # No forward to DOC mean that playbook should be applied
        logger.debug("Started applying ansible playbook")
        ansible_runner_result, fact_cache = run_ansible_playbook(target, username, password, payload)
        if ansible_runner_result.status == "failed":
            send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_EPEM, description="Action application by ePEM has failed")
            raise HTTPException(status_code=500, detail="Execution of Playbook failed. See ePEM DEBUG log for more info.")
        msg_return = RTRRestAnswer(description="Playbook applied", status="success")
        logger.debug(msg_return)
        ##### CALLBACK OK ######
        send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_APPLIED_BY_EPEM, description="Action applied by the ePEM")
        return msg_return
    else:
        # Request should be forwarded to DOC
        doc_mod_info = get_extra("doc_module")
        if actionID is None:
            actionID = str(uuid.uuid4())
        if service is None:
            service = "DNS"  # TODO Workaround
        body: DOCNorthModel = build_request_for_doc(actionid=actionID, target=target, actiontype=action_type, service=service, playbook=payload)
        msg_return = forward_request_to_doc(doc_mod_info, body, actionID, callback_http_url)
        return msg_return


@horse_router.post("/rtr_request", response_model=RTRRestAnswer)
def rtr_request(target_ip: Annotated[str, Query(pattern=IP_PATTERN)], target_port: Optional[Annotated[str, Query(pattern=PORT_PATTERN)]],
                service: str, actionType: RTRActionType, actionID: str, payload: str = Body(None, media_type="application/yaml"),
                callback_http_url: HttpUrl | None = None):
    """
    Integration for HORSE Project. Allow applying mitigation action on a target managed by the NFVCL (ePEM).
    Allows running an ansible playbook on a remote host. The host NEEDS to be managed by nfvcl.

    See Also:

        [HORSE_Demo3_Components_Specification_v0.1](https://tntlabunigeit-my.sharepoint.com/:w:/r/personal/horse-cloud_tnt-lab_unige_it/_layouts/15/Doc.aspx?sourcedoc=%7B34097F2D-C0F8-4E06-B34C-0BA0B3D81DE0%7D&file=HORSE_Demo3_Components_Specification_v0.1.docx&action=default&mobileredirect=true)

    Args:

        target_ip: The IP of the host on which the Ansible playbook is applied ('1.52.65.25' format)

        target_port: The port used by Ansible on the host in which the playbook is applied. This is optional for future use.

        service: str, Service type for our demo 3 "DNS" should be obtained from RTR request

        actionType: str, For this first iteration is always going to be a "Service modification" but for the second iteration should be other type of actions

        actionID: str, this field should be provided by RTR, I think that is really important for the second iteration since we need to control the life cycle of actions, so we should implement it now but could be a dummy parameter for this iteration

        payload: body (yaml), The ansible playbook in yaml format to be applied on the remote target
    """
    dump_playbook(playbook=payload)
    # IF in DEBUG mode, the blueprint manager isn't loaded
    if not os.environ.get('HORSE_DEBUG'):
        bm = get_blueprint_manager()
        vm: VmResource = bm.get_vm_target_by_ip(target_ip)
    else:
        # In DEBUG mode only local target is allowed (ePEM itself)
        if target_ip == "127.0.0.1":
            vm = "not_none"
        else:
            vm=None

    if vm is None:
        # This is the case where the VM is not managed by the ePEM -> Request is forwarded to DOC
        doc_mod_info = get_extra("doc_module")
        body: DOCNorthModel = build_request_for_doc(actionid=actionID, target=target_ip, actiontype=actionType, service=service, playbook=payload)
        msg_return = forward_request_to_doc(doc_mod_info, body, actionID, callback_http_url)
        return msg_return
    else:
        # Action applied by ePEM
        logger.debug("Started applying ansible playbook")
        if not os.environ.get('HORSE_DEBUG'):
            ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, vm.username, vm.password, payload)
        else:
            ansible_runner_result, fact_cache = run_ansible_playbook(target_ip, "ubuntutest", "ubuntutest", payload)
        if ansible_runner_result.status == "failed":
            send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_NOT_APPLIED_BY_EPEM, description="Execution of Playbook failed. See NFVCL DEBUG log for more info.")
            raise HTTPException(status_code=500, detail="Execution of Playbook failed. See NFVCL DEBUG log for more info.")

        msg_return = RTRRestAnswer(description="Playbook applied", status="success")
        send_callback_http(callback_http_url, actionID, callback_code=CallbackCode.ACTION_APPLIED_BY_EPEM, description="Action applied by the ePEM")
        logger.info(msg_return)
        return msg_return


@horse_router.post("/set_doc_ip_port", response_model=RTRRestAnswer)
def set_doc_ip_port(doc_ip: Annotated[str, Query(pattern=IP_PORT_PATTERN)], url_path: Annotated[str, Query(pattern=PATH_PATTERN)]):
    """
    Set up and save the URL of HORSE DOC module. The URL is composed by {doc_ip_port}{url_path}
    """
    insert_extra("doc_module", {"url": f"{doc_ip}{url_path}", "ip": doc_ip, "url_path": url_path})
    msg_return = RTRRestAnswer(description="DOC module IP has been set", status="success")
    logger.info(msg_return.description)
    return msg_return


@horse_router.get("/get_doc_ip_port", response_model=RTRRestAnswer)
def get_doc_ip_port():
    """
    Allows retrieving the DOC URL
    """
    url = get_extra("doc_module")
    return RTRRestAnswer(description="DOC URL", status="success", data=url)
