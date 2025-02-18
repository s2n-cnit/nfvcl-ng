import copy
import ipaddress

import httpx

from nfvcl.blueprints_ng.pdu_configurators.implementations.core_5g.athonet.utils import AthonetAuth
from nfvcl.blueprints_ng.pdu_configurators.types.generic_5g_pdu_configurator import Generic5GConfigurator
from nfvcl_models.blueprint_ng.athonet.core import AthonetAccessToken
from nfvcl_models.blueprint_ng.athonet.upf import AthonetNetworkUpfConfig, AthonetApplicationUpfConfig, DnnVrfMapping
from nfvcl_models.blueprint_ng.g5.upf import UPFBlueCreateModel
from nfvcl_core_models.network import PduModel
from nfvcl_core.utils.log import create_logger

logger = create_logger('AthonetUPFPDUConfigurator')


class AthonetUPFPDUConfigurator(Generic5GConfigurator):
    def __init__(self, pdu_model: PduModel):
        super().__init__(pdu_model)
        self.token, self.refresh_token = self.get_first_token()
        self.mgmt_ip = self.pdu_model.get_mgmt_ip()
        self.athonet_auth = AthonetAuth(self.token, self.refresh_token, mgmt_ip=self.mgmt_ip)
        self.client = httpx.Client(verify=False, auth=self.athonet_auth)
        self.upf_application_config = self.get_upf_application_config()
        self.upf_network_config = self.get_upf_network_config()
        self.dnnvrfmapping = DnnVrfMapping.model_validate(pdu_model.config["dnnvrf"])

    def configure(self, config: UPFBlueCreateModel):
        """
        Configure upf according to UPFBlueCreateModel input
        Args:
            config: Upf configuration model from payload

        """
        logger.info(f"Configuring UPF {self.mgmt_ip}")
        self.upf_application_config.configure(self.dnnvrfmapping.dnns, config)
        updated_config: AthonetApplicationUpfConfig = copy.deepcopy(self.upf_application_config)
        updated_config.version = None
        updated_config.api_version = None
        api_url_ue = f"https://{self.mgmt_ip}/core/upf/api/1/mgmt/config"
        self.client.put(api_url_ue, json=self.upf_application_config.model_dump(exclude_none=True))

    def get_first_token(self):
        """
        Get first pair access token and refresh token

        Returns: Access token and refresh token

        """
        with httpx.Client(http1=False, http2=True, verify=False) as client:
            api_url_ue = f"https://{self.pdu_model.get_mgmt_ip()}/core/pls/api/1/auth/login"
            response = client.post(api_url_ue, json={"username": f"{self.pdu_model.username}", "password": f"{self.pdu_model.password}"})
            t = AthonetAccessToken.model_validate(response.json())
            return f"Bearer {t.access_token}", t.refresh_token

    def get_n_interfaces_ip(self):
        """
        Retrieve N3 and N4 info from Upf

        Returns: n3_ip, n3_cidr, n4_ip, n4_cidr

        """
        logger.info(f"Getting N3 infos")
        n3_ip = ""
        n3_cidr = ""
        n4_ip = ""
        n4_cidr = ""
        for item in self.upf_application_config.gtpu.transports:
            if item.name == "gtpu.n3":
                n3_ip = item.transport_config.local_addr
            elif item.name == "gtpu.n4":
                n4_ip = item.transport_config.local_addr

        for net in self.upf_network_config.networks:
            if net.config.network and net.config.network.vrf == "RAN":
                n3_cidr = ipaddress.ip_interface(net.config.address[0].address).network
            if net.config.network and net.config.network.vrf == "N4":
                n4_cidr = ipaddress.ip_interface(net.config.address[0].address).network

        return n3_ip, n3_cidr, n4_ip, n4_cidr

    def get_upf_application_config(self):
        """

        Returns: model representing upf application config

        """
        api_url_ue = f"https://{self.mgmt_ip}/core/upf/api/1/mgmt/config"
        response = self.client.get(api_url_ue)
        return AthonetApplicationUpfConfig.model_validate(response.json())

    def get_upf_network_config(self):
        """

        Returns: model representing upf network config

        """
        api_url_ue = f"https://{self.mgmt_ip}/core/ncm/api/1/mgmt/config"
        response = self.client.get(api_url_ue)
        return AthonetNetworkUpfConfig.model_validate(response.json())

    def restore_base_config(self, backup_config: AthonetApplicationUpfConfig):
        """
        Restore upf config to a desired one
        Args:
            backup_config: the desired config

        """
        logger.info(f"Restoring UPF to base config")
        backup_config.version = None
        backup_config.api_version = None
        api_url_ue = f"https://{self.mgmt_ip}/core/upf/api/1/mgmt/config"
        self.client.put(api_url_ue, json=backup_config.model_dump(exclude_none=True))
