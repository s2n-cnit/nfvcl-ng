from typing import List

import httpx

from nfvcl.blueprints_ng.pdu_configurators.implementations.core_5g.athonet.utils import AthonetAuth
from nfvcl.blueprints_ng.pdu_configurators.types.generic_5g_pdu_configurator import Generic5GConfigurator
from nfvcl.models.blueprint_ng.Athonet.core import AthonetApplicationCoreConfig, AthonetApplicationAmfConfig, AthonetApplicationSmfConfig, AthonetApplicationUdmConfig, ProvisionedDataProfile, Supi, UserProvisionedDataProfile, AuthenticationSubscription, AthonetAccessToken, ProvisionedDataInfo, Plmns, PlmnsDatum, AvailableSupis, AvailableSupisDatum
from nfvcl.models.blueprint_ng.Athonet.upf import DnnVrfMapping
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel
from nfvcl.models.blueprint_ng.g5.core import Core5GAddSubscriberModel
from nfvcl_core.models.network import PduModel


class AthonetCorePDUConfigurator(Generic5GConfigurator):

    def __init__(self, pdu_model: PduModel):
        super().__init__(pdu_model)
        self.token, self.refresh_token = self.get_first_token()
        self.mgmt_ip = self.pdu_model.get_mgmt_ip()
        self.athonet_auth = AthonetAuth(self.token, self.refresh_token, mgmt_ip=self.mgmt_ip)
        self.client = httpx.Client(verify=False, auth=self.athonet_auth)
        self.core_application_config = self.get_core_config()
        self.dnnvrfmapping = DnnVrfMapping.model_validate(pdu_model.config["dnnvrf"])
        self.upf_ip = pdu_model.config["upf_ip"]

    def configure(self, config: Create5gModel):
        """
       Configure core and add users according to Create5gModel input
        Args:
            config: Core configuration model from payload

        """
        self.core_application_config.amf.configure(config)
        self.core_application_config.smf.configure(self.dnnvrfmapping.dnns, self.upf_ip, config)
        self.core_application_config.udm.configure(config)

        amf_api_url_ue = f"https://{self.mgmt_ip}/core/amf/api/1/mgmt/config"
        smf_api_url_ue = f"https://{self.mgmt_ip}/core/smf/api/1/mgmt/config"
        udm_api_url_ue = f"https://{self.mgmt_ip}/core/udm/api/1/mgmt/config"

        self.client.put(amf_api_url_ue, json=self.core_application_config.amf.model_dump(exclude_none=True, by_alias=True))
        self.client.put(smf_api_url_ue, json=self.core_application_config.smf.model_dump(exclude_none=True, by_alias=True))
        self.client.put(udm_api_url_ue, json=self.core_application_config.udm.model_dump(exclude_none=True, by_alias=True))

        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/plmns"
        self.client.post(udr_api_url_ue, json={"mcc": f"{config.config.plmn[0:3]}", "mnc": f"{config.config.plmn[-2:]}"})

    def get_first_token(self):
        """
        Get first pair access token and refresh token

        Returns: Access token and refresh token

        """
        with httpx.Client(http1=False, http2=True, verify=False) as client:
            api_url_ue = f"https://{self.pdu_model.get_mgmt_ip()}/core/pls/api/1/auth/login"
            response = client.post(api_url_ue, json={"username": f"{self.pdu_model.username}", "password": f"{self.pdu_model.password}"})
            token = AthonetAccessToken.model_validate(response.json())
            return f"Bearer {token.access_token}", token.refresh_token

    def get_amf_ip(self):
        """

        Returns: Amf N2 interface ip

        """
        for item in self.core_application_config.amf.n2_interface.transports:
            if item.name == "default_n2":
                return item.transport_config.local_addrs[0]

    def get_core_config(self):
        """
        Returns: model containing all crucial NF config (AMF, SMF and UDM)

        """
        athonet_core_config = AthonetApplicationCoreConfig()
        athonet_core_config.amf = AthonetApplicationAmfConfig.model_validate(self.client.get(f"https://{self.mgmt_ip}/core/amf/api/1/mgmt/config").json())
        athonet_core_config.smf = AthonetApplicationSmfConfig.model_validate(self.client.get(f"https://{self.mgmt_ip}/core/smf/api/1/mgmt/config").json())
        athonet_core_config.udm = AthonetApplicationUdmConfig.model_validate(self.client.get(f"https://{self.mgmt_ip}/core/udm/api/1/mgmt/config").json())

        return athonet_core_config

    def add_provisioned_data_profile(self, subscriber_model: Core5GAddSubscriberModel, add_infos: List[ProvisionedDataInfo]):
        """
        Add provisioned data profile for a specific subscriber
        Args:
            subscriber_model: user model info
            add_infos: list of user's slices associated with their dnns

        Returns: uuid of provisioned data profile created

        """
        provisioned_data = ProvisionedDataProfile()
        provisioned_data.configure(subscriber_model, add_infos)
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/provisioned_data_profiles"
        response = self.client.post(udr_api_url_ue, json=provisioned_data.model_dump(exclude_none=True, by_alias=True))
        return response.json()["uuid"]

    def delete_provisioned_data_profile(self, uuid: str):
        """
        Delete provisioned data profile for a specific subscriber
        Args:
            uuid: uuid of provisioned data profile

        """
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/provisioned_data_profiles/{uuid}"
        code = 0
        while code != 204:
            response = self.client.delete(udr_api_url_ue)
            code = response.status_code

    def add_user(self, subscriber_model: Core5GAddSubscriberModel, add_infos: List[ProvisionedDataInfo]):
        """
        Add user and his provisioned data profile (calling ADD_PROVISIONED_DATA_PROFILE)
        Args:
            subscriber_model: user model info
            add_infos: list of user's slices associated with their dnns

        Returns: uuid of provisioned data profile

        """
        uuid = self.add_provisioned_data_profile(subscriber_model, add_infos)
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/supis"
        supi = Supi(
            supi=f"imsi-{subscriber_model.imsi}",
            provisioned_data_profile=UserProvisionedDataProfile(
                uuid=uuid
            ),
            authentication_subscription=AuthenticationSubscription(
                k=subscriber_model.k,
                opc=subscriber_model.opc
            )
        )
        self.client.post(udr_api_url_ue, json=supi.model_dump(exclude_none=True, by_alias=True))
        return uuid

    def del_user(self, imsi: str, uuid: str = None):
        """
        Delete user and his associated provisioned data profile
        Args:
            imsi: user's imsi
            uuid: provisioned data profile uuid

        """
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/supis/{imsi}"
        code = 0
        while code != 204:
            response = self.client.delete(udr_api_url_ue)
            code = response.status_code
        if uuid:
            self.delete_provisioned_data_profile(uuid)

    def restore_base_config(self, backup_config: AthonetApplicationCoreConfig):
        """
        Restore core config to a desired one, deleting all plmns and supis from UDR
        Args:
            backup_config: the desired config

        """
        amf_api_url_ue = f"https://{self.mgmt_ip}/core/amf/api/1/mgmt/config"
        smf_api_url_ue = f"https://{self.mgmt_ip}/core/smf/api/1/mgmt/config"
        udm_api_url_ue = f"https://{self.mgmt_ip}/core/udm/api/1/mgmt/config"

        self.client.put(amf_api_url_ue, json=backup_config.amf.model_dump(exclude_none=True, by_alias=True))
        self.client.put(smf_api_url_ue, json=backup_config.smf.model_dump(exclude_none=True, by_alias=True))
        self.client.put(udm_api_url_ue, json=backup_config.udm.model_dump(exclude_none=True, by_alias=True))

        self.delete_all_supis()
        self.delete_all_udr_plmns()

    def get_available_udr_plmns(self) -> List[PlmnsDatum]:
        """

        Returns: all available plmns of UDR

        """
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/plmns"
        response = self.client.get(udr_api_url_ue)
        available_plmns = Plmns.model_validate(response.json())
        return available_plmns.data

    def delete_all_udr_plmns(self):
        """
        Delete all available plmns of UDR

        """
        plmns = self.get_available_udr_plmns()
        for plmn in plmns:
            udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/plmns/{plmn.mcc}-{plmn.mnc}"
            self.client.delete(udr_api_url_ue)

    def list_connected_supis(self) -> List[str]:
        """

        Returns: list of all connected supis to the AMF

        """
        amf_api_url_ue = f"https://{self.mgmt_ip}/core/amf/api/1/ue/status/supis"
        response = self.client.get(amf_api_url_ue)
        return response.json()

    def detach_all_ues(self):
        """

        Detach all connected supis from the AMF

        """
        ues = self.list_connected_supis()
        for ue in ues:
            amf_api_url_ue = f"https://{self.mgmt_ip}/core/amf/api/1/ue/status/supis/{ue}/remove"
            self.client.post(amf_api_url_ue)

    def list_all_supis(self) -> List[AvailableSupisDatum]:
        """

        Returns: list all available supis

        """
        udr_api_url_ue = f"https://{self.mgmt_ip}/core/udr/api/1/provisioning/supis"
        response = self.client.get(udr_api_url_ue)
        return AvailableSupis.model_validate(response.json()).data

    def delete_all_supis(self):
        """

        Delete all available supis

        """
        self.detach_all_ues()
        supis = self.list_all_supis()
        for supi in supis:
            if supi.authentication_subscription:
                self.del_user(supi.supi, supi.provisioned_data_profile.uuid)
            else:
                self.del_user(supi.supi)
