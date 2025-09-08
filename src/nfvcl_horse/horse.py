import logging
import os
import uuid
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Union, Dict, Any, Optional

import httpx
from fastapi import HTTPException, Query
from pydantic import Field

from nfvcl_core.nfvcl_main import NFVCL
from nfvcl_core.nfvcl_main import NFVCLPublic, NFVCLPublicMethod
from nfvcl_core.plugins.plugin import NFVCLPlugin
from nfvcl_core.providers.configurators.ansible_utils import run_ansible_playbook
from nfvcl_core.utils.file_utils import create_tmp_file
from nfvcl_core.utils.log import create_logger
from nfvcl_core.utils.util import IP_PATTERN, PATH_PATTERN
from nfvcl_core_models.base_model import NFVCLBaseModel
from nfvcl_core_models.network.ipam_models import SerializableIPv4Address
from nfvcl_core_models.resources import VmResource

HORSE_DEFAULT_TIMEOUT = 60
HORSE_ERROR_TIMEOUT = 90
TIMEOUT = HORSE_ERROR_TIMEOUT

DUMP_FOLDER = '/tmp/ePEM/received_playbooks/'
Path(DUMP_FOLDER).mkdir(parents=True, exist_ok=True)


############################
#       DATA MODELS        #
############################

class MitigationActionModel(NFVCLBaseModel):
    command: str = Field(default="add", examples=["add"])  # Example for Swagger UI
    intent_type: str = Field(..., examples=["mitigation"])
    intent_id: str = Field(..., examples=["ABC124"])  # Made intent_id required (not optional)
    threat: str = Field(default="", examples=["ddos"])
    target_domain: str = Field(default="", examples=["example.com"])
    # Changed to Union[str, Dict[str, Any]] to accept either a string or a structured object
    action: Union[str, Dict[str, Any]] = Field(..., examples=[
        "Can use a string like 'rate limit DNS server at ip 10.10.2.1 at port 123, for 20 requests per second' "
    ])

    attacked_host: SerializableIPv4Address = Field(default="0.0.0.0", examples=["10.0.0.1"])
    mitigation_host: str = Field(default="0.0.0.0", examples=["172.16.2.1"])
    duration: int = Field(default=0, examples=[7000])
    status: str = Field(default="pending", examples=["completed"], description="Current status of the mitigation action")
    info: str = Field(default="to be enforced", examples=["Action successfully executed"], description="Additional information about the action status")
    ansible_command: str = Field(default="", examples=["- hosts: [172.16.2.1]\n  tasks:\n..."], description="The generated Ansible playbook command")
    testbed: Optional[str] = Field(default="upc", examples=["upc"], description="The testbed name")


class DocModuleInfo(NFVCLBaseModel):
    ipaddress: SerializableIPv4Address
    port: int = Field(None, ge=0, le=65535)
    path: str = Field(description="Path to the module expresses like /path1/path2", pattern=PATH_PATTERN)

    def url(self):
        return f"{self.ipaddress}:{self.port}{self.path}"


class RTRRestAnswer(NFVCLBaseModel):
    """
    Represents the response model for RTR REST operations.

    Attributes:
        description (str): A brief message or explanation regarding the
            operation outcome. Defaults to 'operation submitted'.
        status (str): A status indicator of the operation, such as 'submitted'.
        status_code (int): HTTP status code associated with the operation
            response. Defaults to 202 (Accepted).
        data (dict): Additional data or information related to the operation,
            represented as a dictionary. Defaults to an empty dictionary.
    """
    description: str = 'operation submitted'
    status: str = 'submitted'
    status_code: int = 202  # OK
    data: dict = {}


######################
#    PLUGIN HORSE    #
######################

class NFVCLHorsePlugin(NFVCLPlugin):
    logger: logging.Logger

    def __init__(self, nfvcl_context: NFVCL):
        super().__init__(nfvcl_context, "HorsePlugin")
        self.logger = create_logger("Horse REST")

    def load(self):
        print(f"Loading {self.name}")

    def dump_playbook(self, playbook: str):
        """
        Dumps the given playbook content into a uniquely named temporary YAML file.

        The method writes the YAML-formatted playbook content into a uniquely named
        temporary file for logging or debugging purposes. It generates a file name
        using the current timestamp and a random UUID.

        Args:
            playbook: The YAML-formatted playbook content as a string.
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

    def forward_request_to_doc(self, doc_request: MitigationActionModel):
        """
        Forwards a request to the DOC module and handles the response.

        This method sends a mitigation action request to the configured DOC module by performing an HTTP POST request.
        If the DOC module is not configured or there are connection issues, appropriate HTTP exceptions are raised.

        Args:
            doc_request (MitigationActionModel): The mitigation action request that needs to be forwarded to the
                DOC module.

        Raises:
            HTTPException: Either when the DOC module is not configured, there is a connection error, a
                timeout occurred, or when the HTTP response status from the DOC module is not 200.

        Returns:
            RTRRestAnswer: Contains the response description, status, status code, and additional debug information
                retrieved from the DOC module response.
        """
        doc_info = self.nfvcl_context.extra_repository.find_one("doc_module")
        if doc_info is None:
            raise HTTPException(status_code=HTTPStatus.PRECONDITION_REQUIRED, detail="DOC module is not configured, you should set using the appropriate API (/set_doc_ip_port)")
        doc_mod_info = DocModuleInfo.model_validate(doc_info)
        try:
            # Trying sending request to DOC
            self.logger.info(f"Sending request to DOC: \n {doc_request.model_dump_json()}")
            data = doc_request.model_dump_json(exclude_none=True)
            doc_response = httpx.post(f"http://{doc_mod_info.url()}", data=data, headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
            # Returning the code that
            if doc_response.status_code != HTTPStatus.OK.value:
                raise HTTPException(status_code=doc_response.status_code, detail=f"DOC response code is different from 200: {doc_response.text}")
        except httpx.ReadTimeout:
            self.logger.error(f"Connection Timeout to DOC module at http://{doc_mod_info.url()}")
            raise HTTPException(status_code=HTTPStatus.GATEWAY_TIMEOUT, detail=f"Cannot contact DOC module at http://{doc_mod_info.url()}")
        except httpx.ConnectError:
            self.logger.error(f"Connection Error to DOC module (refused at http://{doc_mod_info.url()})")
            raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail=f"Connection refused by DOC module at http://{doc_mod_info.url()}")

        doc_response_debug = {"url": str(doc_response.url), "Params": str(doc_response.headers), "Body": doc_response.text}
        self.logger.debug(f"DOC response\n{doc_response_debug}")
        return RTRRestAnswer(description=f"The request has been forwarded to DOC module", status="forwarded", status_code=200, data=doc_response_debug)

    @NFVCLPublic(path="/rtr_request", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.POST, sync=True)
    def rtr_request(self, mitigation_model: MitigationActionModel) -> RTRRestAnswer:
        """
        Processes an RTR (Runtime Threat Response) request by applying an Ansible playbook based on the given mitigation model.
        The request can either be handled locally by ePEM or forwarded to a downstream component if the target Virtual Machine (VM)
        is not managed by ePEM.

        Args:
            mitigation_model (MitigationActionModel): A model containing details of the Ansible playbook command
                to be executed and the mitigation host along with other necessary attributes.

        Returns:
            RTRRestAnswer: An object containing the status and description of the operation.

        Raises:
            HTTPException: If the execution of the Ansible playbook fails.
        """
        self.dump_playbook(playbook=mitigation_model.ansible_command)
        # IF in DEBUG mode, the blueprint manager isn't loaded
        if not os.environ.get('HORSE_DEBUG'):
            blueprint_manager = self.nfvcl_context.blueprint_manager
            vm: VmResource | None = blueprint_manager.get_vm_target_by_ip(mitigation_model.mitigation_host)
        else:
            # In DEBUG mode only local target is allowed (ePEM itself)
            if mitigation_model.mitigation_host == "127.0.0.1":
                vm = "not_none"
            else:
                vm = None

        if vm is None:
            # This is the case where the VM is not managed by the ePEM -> Request is forwarded to DOC
            msg_return = self.forward_request_to_doc(mitigation_model)
            return msg_return
        else:
            # Action applied by ePEM
            self.logger.debug("Started applying ansible playbook")
            ansible_runner_result, fact_cache = run_ansible_playbook(mitigation_model.mitigation_host, vm.username, vm.password, mitigation_model.ansible_command)
            if ansible_runner_result.status == "failed":
                raise HTTPException(status_code=500, detail="Execution of Playbook failed. See ePEM DEBUG log for more info (http://ePEM_IP:5002/logs).")

            msg_return = RTRRestAnswer(description="Playbook applied", status="success")
            self.logger.info(msg_return)
            return msg_return

    @NFVCLPublic(path="/set_doc_ip_port", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.POST, sync=True)
    def set_doc_ip_port(self, doc_ip: Annotated[str, Query(pattern=IP_PATTERN)], doc_port: Annotated[int, Query(ge=0, le=65535)], path: Annotated[str, Query(pattern=PATH_PATTERN)]) -> RTRRestAnswer:
        """
        Sets the IP address, port, and path for the DOC module. This method updates the
        DOC module configuration using the provided IP, port, and path, and saves the
        updated information to the repository. After successful execution, a response
        message indicating the successful update is logged and returned.

        Args:
            doc_ip (str): The IP address of the DOC module. Must conform to the specified
                IP pattern.
            doc_port (int): The port number for the DOC module. Must be between 0 and 65535
                inclusive.
            path (str): The path for the DOC module. Must conform to the specified path
                pattern.

        Returns:
            RTRRestAnswer: An object containing the description and status of the
                operation.
        """
        module_info = DocModuleInfo(ipaddress=doc_ip, port=doc_port, path=path)
        self.nfvcl_context.extra_repository.save("doc_module", module_info.model_dump())
        msg_return = RTRRestAnswer(description="DOC module IP has been set", status="success")
        self.logger.info(msg_return.description)
        return msg_return

    @NFVCLPublic(path="/get_doc_ip_port", section=NFVCL.HORSE_SECTION, method=NFVCLPublicMethod.GET, sync=True)
    def get_doc_ip_port(self) -> RTRRestAnswer:
        """
        Handles HTTP GET requests for fetching the IP and port details of the DOC module.

        This method interacts with the NFVCL context to retrieve configuration details
        for the DOC module. If the DOC module is not configured, it raises an HTTP
        exception with a 404 status code. Once successfully retrieved, the DOC module
        details are validated and returned within an RTRRestAnswer object.

        Raises:
            HTTPException: If the DOC module configuration is not found.

        Returns:
            RTRRestAnswer: An object containing status, description, and data pertaining
            to the DOC module configuration.
        """
        doc_info = self.nfvcl_context.extra_repository.find_one("doc_module")
        if doc_info is None:
            raise HTTPException(status_code=404, detail="DOC module is not configured, you should set using the appropriate API.")
        doc_mod_info = DocModuleInfo.model_validate(doc_info)
        return RTRRestAnswer(description="DOC URL has been set", status="success", data=doc_mod_info.model_dump())
