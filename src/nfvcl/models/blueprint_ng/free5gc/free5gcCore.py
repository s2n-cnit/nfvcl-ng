from __future__ import annotations
from typing import Optional, List, Dict, Union, Literal, Annotated
from pydantic import Field, RootModel, field_validator

from nfvcl.models.base_model import NFVCLBaseModel
import re

from nfvcl.models.blueprint_ng.core5g.common import Create5gModel, SstConvertion

ok_regex = re.compile(r'^([a-fA-F0-9]{6})$')


class Service(NFVCLBaseModel):
    name: str
    type: str
    port: int
    node_port: str = Field(..., alias='nodePort')


class Nrf(NFVCLBaseModel):
    service: Service


class Sbi(NFVCLBaseModel):
    scheme: str


class N2if(NFVCLBaseModel):
    ip_address: str = Field(..., alias='ipAddress')


class Ngap(NFVCLBaseModel):
    enabled: bool
    name: str
    port: int
    nodeport: int
    protocol: str
    type: str


class AmfService(NFVCLBaseModel):
    ngap: Ngap


class Amf(NFVCLBaseModel):
    n2if: N2if
    service: AmfService = Field(..., alias='service')


class N4if(NFVCLBaseModel):
    ip_address: str = Field(..., alias='ipAddress')


class Smf(NFVCLBaseModel):
    n4if: N4if


class Global(NFVCLBaseModel):
    name: str
    user_plane_architecture: str = Field(..., alias='userPlaneArchitecture')
    nrf: Nrf
    sbi: Sbi
    amf: Amf
    smf: Smf


class Auth(NFVCLBaseModel):
    enabled: bool


class Persistence(NFVCLBaseModel):
    enabled: bool
    size: str
    mount_path: str = Field(..., alias='mountPath')


class Mongodb(NFVCLBaseModel):
    fullname_override: str = Field(..., alias='fullnameOverride')
    use_stateful_set: bool = Field(..., alias='useStatefulSet')
    auth: Auth
    persistence: Persistence
    service: Service = Field(None, alias='service')


class Logger(NFVCLBaseModel):
    enable: bool
    level: str
    report_caller: bool = Field(..., alias='reportCaller')


class Free5gcCoreConfig(NFVCLBaseModel):
    global_: Global = Field(..., alias='global')
    deploy_mongo_db: bool = Field(..., alias='deployMongoDb')
    deploy_amf: bool = Field(..., alias='deployAmf')
    deploy_ausf: bool = Field(..., alias='deployAusf')
    deploy_n3iwf: bool = Field(..., alias='deployN3iwf')
    deploy_nrf: bool = Field(..., alias='deployNrf')
    deploy_nssf: bool = Field(..., alias='deployNssf')
    deploy_pcf: bool = Field(..., alias='deployPcf')
    deploy_smf: bool = Field(..., alias='deploySmf')
    deploy_udm: bool = Field(..., alias='deployUdm')
    deploy_udr: bool = Field(..., alias='deployUdr')
    deploy_upf: bool = Field(..., alias='deployUpf')
    deploy_webui: bool = Field(..., alias='deployWebui')
    deploy_db_python: bool = Field(..., alias='deployDbPython')
    mongodb: Mongodb
    free5gc_amf: Free5gcAmf = Field(..., alias='free5gc-amf')
    free5gc_smf: Free5gcSmf = Field(..., alias='free5gc-smf')
    free5gc_ausf: Free5gcAusf = Field(..., alias='free5gc-ausf')
    free5gc_n3iwf: Optional[Free5gcN3iwf] = Field(None, alias='free5gc-n3iwf')
    free5gc_nrf: Free5gcNrf = Field(..., alias='free5gc-nrf')
    free5gc_nssf: Free5gcNssf = Field(..., alias='free5gc-nssf')
    free5gc_pcf: Free5gcPcf = Field(..., alias='free5gc-pcf')
    free5gc_udm: Free5gcUdm = Field(..., alias='free5gc-udm')
    free5gc_udr: Free5gcUdr = Field(..., alias='free5gc-udr')
    free5gc_chf: Free5gcChf = Field(..., alias='free5gc-chf')
    free5gc_nef: Free5gcNef = Field(..., alias='free5gc-nef')

    ###############################################################################
    ##################################### GLOBAL ##################################
    ###############################################################################

    def set_smf_ip(self, ip: str):
        """
        Args:
            ip: ip to set

        """
        self.global_.smf.n4if.ip_address = ip

    ###############################################################################
    ##################################### NRF #####################################
    ###############################################################################

    def set_default_nrf_plmnd(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmnid = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        self.free5gc_nrf.nrf.configuration.nrf_configuration.default_plmn_id = plmnid

    ###############################################################################
    ##################################### AMF #####################################
    ###############################################################################

    def add_item_amf_servedGuamiList(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmnid = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        item = ServedGuamiListItem(
            plmn_id=plmnid,
            amf_id="cafe00"
        )
        if item not in self.free5gc_amf.amf.configuration.amf_configuration.served_guami_list:
            self.free5gc_amf.amf.configuration.amf_configuration.served_guami_list.append(item)

    def add_item_amf_supportTaiList(self, mcc: str, mnc: str, tac: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            tac: tracking area code

        """
        plmnid = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        item = SupportTaiListItem(
            plmn_id=plmnid,
            tac=tac
        )
        if item not in self.free5gc_amf.amf.configuration.amf_configuration.support_tai_list:
            self.free5gc_amf.amf.configuration.amf_configuration.support_tai_list.append(item)

    def create_plmn_amf_list(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmn_item = PlmnSupportListItem(
            plmn_id=PlmnId(
                mcc=mcc,
                mnc=mnc
            ),
            snssai_list=[]
        )
        if any(item.plmn_id.mcc == mcc and item.plmn_id.mnc == mnc for item in self.free5gc_amf.amf.configuration.amf_configuration.plmn_support_list):
            return
        self.free5gc_amf.amf.configuration.amf_configuration.plmn_support_list.append(plmn_item)

    def add_plmn_amf_item(self, mcc: str, mnc: str, area_id: int, nssai: Snssai):
        """
        Add slice to PlmnSupportListItem, if no PlmnSupportListItem available it will create.
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            area_id: nssai's area id
            nssai: nssai to add

        """
        for item in self.free5gc_amf.amf.configuration.amf_configuration.plmn_support_list:
            if item.plmn_id.mcc == mcc and item.plmn_id.mnc == mnc:
                if nssai not in item.snssai_list:
                    item.snssai_list.append(nssai)
                return
        self.create_plmn_amf_list(mcc, mnc)
        self.add_plmn_amf_item(mcc, mnc, area_id, nssai)

    def add_dnn_amf_item(self, dnn: str):
        """
        Args:
            dnn: dnn name

        """
        if dnn not in self.free5gc_amf.amf.configuration.amf_configuration.support_dnn_list:
            self.free5gc_amf.amf.configuration.amf_configuration.support_dnn_list.append(dnn)

    ###############################################################################
    ##################################### SMF #####################################
    ###############################################################################

    def create_ssnsai_smf_item(self, ssnsai: Snssai):
        """
        Args:
            ssnsai: snssai to add

        """
        snssainfo_item = SnssaiInfo(
            s_nssai=ssnsai,
            dnn_infos=[]
        )
        if any(item.s_nssai == ssnsai for item in self.free5gc_smf.smf.configuration.smf_configuration.snssai_infos):
            return
        self.free5gc_smf.smf.configuration.smf_configuration.snssai_infos.append(snssainfo_item)

    def add_dnn_info_smf_item(self, dnn: str, ipv4: str, snssai: Snssai, ipv6=None):
        """
        Args:
            dnn: dnn name
            ipv4: ipv4 to add
            snssai: snssai to which to add the dnn info
            ipv6: ipv6 to add (optional)

        """
        dnn_item = DnnInfo(
            dnn=dnn,
            dns=Dns(
                ipv4=ipv4,
                ipv6=ipv6
            )
        )
        for item in self.free5gc_smf.smf.configuration.smf_configuration.snssai_infos:
            if item.s_nssai == snssai:
                if dnn_item not in item.dnn_infos:
                    item.dnn_infos.append(dnn_item)
                return True
        self.create_ssnsai_smf_item(snssai)
        self.add_dnn_info_smf_item(dnn, ipv4, snssai)

    def add_plmn_smf_item(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmnid = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        if plmnid not in self.free5gc_smf.smf.configuration.smf_configuration.plmn_list:
            self.free5gc_smf.smf.configuration.smf_configuration.plmn_list.append(plmnid)

    def add_node_smf_topology(self, node_name: str, node: Node):
        """
        Args:
            node_name: the name ot the node
            node: the node to add (could be gNB or UPF)

        """
        if node_name not in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root.keys():
            self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root[node_name] = node

    def add_gnb_smf(self, gnb_name: str):
        """
        Add a gnb node to smf topology
        Args:
            gnb_name: gnb node name

        """
        node = GNb(type="AN")
        self.add_node_smf_topology(gnb_name, node)

    def add_upf_smf(self, upf_name: str, ip: str, n3ip: str):
        """
        Add a upf node to smf topology
        Args:
            upf_name: upf node name
            ip: ip to communicate with the smf
            n3ip: N3 interface's ip

        """
        node = Upf(
            type="UPF",
            node_id=ip,
            addr=ip,
            s_nssai_upf_infos=[],
            interfaces=[Interface(
                interface_type="N3",
                endpoints=[n3ip],
                network_instances=[]
            )])
        self.add_node_smf_topology(upf_name, node)

    def add_snssaiupfinfos_smf(self, gnb_name: str, upf_name: str, upf_ip: str, upfn3_ip: str, sst: int, sd: str):
        """
        Args:
            gnb_name: gnb node name to associate with upf
            upf_name: upf node name to associate with gnb
            upf_ip: ip to communicate with the smf
            upfn3_ip: N3 interface's ip
            sst: slice type
            sd: slice id

        """
        if upf_name in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root.keys():
            for upf_info in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root[upf_name].s_nssai_upf_infos:
                if upf_info.s_nssai.sst == sst and upf_info.s_nssai.sd == sd:
                    return
            snssai_upf = SNssaiUpfInfo(
                s_nssai=Snssai(
                    sst=sst,
                    sd=sd),
                dnn_upf_info_list=[]
            )
            self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root[upf_name].s_nssai_upf_infos.append(snssai_upf)
            return
        self.add_upf_smf(upf_name, upf_ip, upfn3_ip)
        self.add_gnb_smf(gnb_name)
        self.add_link_smf(upf_name, gnb_name)
        self.add_snssaiupfinfos_smf(gnb_name, upf_name, upf_ip, upfn3_ip, sst, sd)

    def add_dnnupfinfolist_smf(self, gnb_name: str, upf_name: str, upf_ip: str, upfn3_ip: str, sst: int, sd: str, dnn_name: str, ip_pool: str):
        """
        Args:
            gnb_name: gnb node name to associate with upf
            upf_name: upf node name to associate with gnb
            upf_ip: ip to communicate with the smf
            upfn3_ip: N3 interface's ip
            sst: slice type
            sd: slice id
            dnn_name: dnn name
            ip_pool: dnn cidr

        """
        if upf_name in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root.keys():
            for upf_info in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root[upf_name].s_nssai_upf_infos:
                if upf_info.s_nssai.sst == sst and upf_info.s_nssai.sd == sd:
                    for dnn in upf_info.dnn_upf_info_list:
                        if dnn.dnn == dnn_name:
                            return
                    dnn = DnnUpfInfoListItem(
                        dnn=dnn_name,
                        pools=[Pool(cidr=ip_pool)]
                    )
                    upf_info.dnn_upf_info_list.append(dnn)
                    self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root[upf_name].interfaces[0].network_instances.append(dnn.dnn)
                    return
        self.add_snssaiupfinfos_smf(gnb_name, upf_name, upf_ip, upfn3_ip, sst, sd)
        self.add_dnnupfinfolist_smf(gnb_name, upf_name, upf_ip, upfn3_ip, sst, sd, dnn_name, ip_pool)

    def add_link_smf(self, upf_name: str, gnb_name: str):
        """
        Associate gNB and UPF
        Args:
            upf_name: upf node name
            gnb_name: gnb node name

        """
        for link in self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.links:
            if link.a == upf_name and link.b == gnb_name:
                return
        link = Link(
            a=gnb_name,
            b=upf_name
        )
        self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.links.append(link)

    ################################################################################
    ##################################### AUSF #####################################
    ################################################################################

    def add_plmn_ausf_item(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmnid = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        if plmnid not in self.free5gc_ausf.ausf.configuration.ausf_configuration.plmn_support_list:
            self.free5gc_ausf.ausf.configuration.ausf_configuration.plmn_support_list.append(plmnid)

    #################################################################################
    ##################################### NSSF #####################################
    #################################################################################

    def add_supported_plmn_nssf(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc

        """
        plmn = PlmnId(
            mcc=mcc,
            mnc=mnc
        )
        if plmn not in self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_plmn_list:
            self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_plmn_list.append(plmn)

    def create_supportednssaiInplmnlist_nssf(self, mcc: str, mnc: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc


        """
        item = SupportedNssaiInPlmnListItem(
            plmn_id=PlmnId(
                mcc=mcc,
                mnc=mnc
            ),
            supported_snssai_list=[]
        )
        if any(item.plmn_id.mcc == mcc and item.plmn_id.mnc == mnc for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_nssai_in_plmn_list):
            return
        self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_nssai_in_plmn_list.append(item)

    def add_supportedsnssailist_item_nssf(self, mcc: str, mnc: str, snssai: Snssai):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            snssai: snssai to add

        """
        for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_nssai_in_plmn_list:
            if item.plmn_id.mcc == mcc and item.plmn_id.mnc == mnc and snssai not in item.supported_snssai_list:
                item.supported_snssai_list.append(snssai)
                return
        self.create_supportednssaiInplmnlist_nssf(mcc, mnc)
        self.add_supportedsnssailist_item_nssf(mcc, mnc, snssai)

    def add_nsi_list_item_nssf(self, sst: int, sd: str, nsi_id: int):
        """
        Args:
            sst: slice type
            sd: slice id
            nsi_id: unique id, starting from 1

        Returns:

        """
        if any(item.snssai.sst == sst and item.snssai.sd == sd for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.nsi_list):
            return
        item = NsiListItem(
            snssai=Snssai(
                sst=sst,
                sd=sd
            ),
            nsi_information_list=[
                NsiInformationListItem(
                    nrf_id=f"{self.global_.sbi.scheme}://{self.global_.nrf.service.name}:{self.global_.nrf.service.port}/nnrf-nfm/v1/nf-instances",
                    nsi_id=nsi_id
                )
            ]
        )
        self.free5gc_nssf.nssf.configuration.nssf_configuration.nsi_list.append(item)

    def create_amf_set_list_nssf(self, id: int):
        """
        Args:
            id: unique id, starting from 1

        """
        if any(item.amf_set_id == id for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_set_list):
            return
        item = AmfSetListItem(
            amf_set_id=id,
            nrf_amf_set=f"{self.global_.sbi.scheme}://{self.global_.nrf.service.name}:{self.global_.nrf.service.port}/nnrf-nfm/v1/nf-instances",
            supported_nssai_availability_data=[]
        )
        self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_set_list.append(item)

    def add_supported_nssai_availability_datum_nssf(self, id: int, mcc: str, mnc: str, tac: str):
        """
        Args:
            id: unique id, starting from 1
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            tac: tracking area code of the snssai

        Returns:

        """
        for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_set_list:
            if item.amf_set_id == id:
                if any(el.tai.tac == tac and el.tai.plmn_id.mcc == mcc and el.tai.plmn_id.mnc == mnc for el in item.supported_nssai_availability_data):
                    return
                tai = SupportedNssaiAvailabilityDatum(
                    tai=Tai(
                        plmn_id=PlmnId(
                            mcc=mcc,
                            mnc=mnc
                        ),
                        tac=tac
                    ),
                    supported_snssai_list=[]
                )
                item.supported_nssai_availability_data.append(tai)
                return
        self.create_amf_set_list_nssf(id)
        self.add_supported_nssai_availability_datum_nssf(id, mcc, mnc, tac)

    def add_supported_nssai_nssf(self, id: int, mcc: str, mnc: str, tac: str, snssai: Snssai):
        """
        Args:
            id: unique id, starting from 1
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            tac: tracking area code of the snssai
            snssai: snssai

        """
        for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_set_list:
            if item.amf_set_id == id:
                for el in item.supported_nssai_availability_data:
                    if el.tai.tac == tac and el.tai.plmn_id.mcc == mcc and el.tai.plmn_id.mnc == mnc and snssai not in el.supported_snssai_list:
                        el.supported_snssai_list.append(snssai)
                        return
        self.add_supported_nssai_availability_datum_nssf(id, mcc, mnc, tac)
        self.add_supported_nssai_nssf(id, mcc, mnc, tac, snssai)

    def create_talist_item_nssf(self, mcc: str, mnc: str, tac: str):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            tac: tracking area code of the snssai

        """
        if any(el.tai.tac == tac for el in self.free5gc_nssf.nssf.configuration.nssf_configuration.ta_list):
            return
        item = TaListItem(
            tai=Tai(
                plmn_id=PlmnId(
                    mcc=mcc,
                    mnc=mnc
                ),
                tac=tac
            ),
            access_type="3GPP_ACCESS",
            supported_snssai_list=[]
        )
        self.free5gc_nssf.nssf.configuration.nssf_configuration.ta_list.append(item)

    def add_tai_supportedsnssailist_nssf_item(self, mcc: str, mnc: str, tac: str, snssai: Snssai):
        """
        Args:
            mcc: PLMN's mcc
            mnc: PLMN's mnc
            tac: tracking area code of the snssai
            snssai: snssai


        """
        for item in self.free5gc_nssf.nssf.configuration.nssf_configuration.ta_list:
            if item.tai.tac == tac:
                if snssai not in item.supported_snssai_list:
                    item.supported_snssai_list.append(snssai)
                    return
        self.create_talist_item_nssf(mcc, mnc, tac)
        self.add_tai_supportedsnssailist_nssf_item(mcc, mnc, tac, snssai)

    def clear_core_values(self):
        """
        Clear all config values

        """
        #### AMF ####
        self.free5gc_amf.amf.configuration.amf_configuration.served_guami_list.clear()
        self.free5gc_amf.amf.configuration.amf_configuration.support_tai_list.clear()
        self.free5gc_amf.amf.configuration.amf_configuration.plmn_support_list.clear()
        self.free5gc_amf.amf.configuration.amf_configuration.support_dnn_list.clear()

        #### SMF ####
        self.free5gc_smf.smf.configuration.smf_configuration.snssai_infos.clear()
        self.free5gc_smf.smf.configuration.smf_configuration.plmn_list.clear()
        self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.up_nodes.root.clear()
        self.free5gc_smf.smf.configuration.smf_configuration.userplane_information.links.clear()
        # self.state.free5gc_config_values.free5gc_smf.smf.configuration.ue_routing_info.root.clear()

        #### AUSF ####
        self.free5gc_ausf.ausf.configuration.ausf_configuration.plmn_support_list.clear()

        #### N3IWF ####
        # self.state.free5gc_config_values.free5gc_n3iwf.n3iwf.configuration.n3iwf_configuration.n3_iwf_information.supported_ta_list.clear()

        #### NSSF ####
        self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_plmn_list.clear()
        self.free5gc_nssf.nssf.configuration.nssf_configuration.supported_nssai_in_plmn_list.clear()
        # self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_list.clear()
        self.free5gc_nssf.nssf.configuration.nssf_configuration.ta_list.clear()
        # self.free5gc_nssf.nssf.configuration.nssf_configuration.mapping_list_from_plmn.clear()
        self.free5gc_nssf.nssf.configuration.nssf_configuration.amf_set_list.clear()
        self.free5gc_nssf.nssf.configuration.nssf_configuration.nsi_list.clear()


############################################### SMF ##################################################

class Snssai(NFVCLBaseModel):
    sst: int
    sd: str

    @field_validator('sd')
    def field_checker(cls, v):
        if len(v) <= 6:
            v = v.zfill(6)
            ok = ok_regex.search(v) is not None
            if ok:
                return v
        raise Exception("Slice must be in range 000000~FFFFFF")


class Dns(NFVCLBaseModel):
    ipv4: str
    ipv6: Optional[str] = Field(default=None)


class DnnInfo(NFVCLBaseModel):
    dnn: str
    dns: Dns


class SnssaiInfo(NFVCLBaseModel):
    s_nssai: Snssai = Field(..., alias='sNssai')
    dnn_infos: List[DnnInfo] = Field(..., alias='dnnInfos')
    dnaiList: List[str] = Field(default=["mec"], alias='dnaiList')


class GNb(NFVCLBaseModel):
    type: Literal['AN']


class Pool(NFVCLBaseModel):
    cidr: str


class StaticPool(NFVCLBaseModel):
    cidr: str


class DnnUpfInfoListItem(NFVCLBaseModel):
    dnn: str
    pools: List[Pool]
    static_pools: Optional[List[StaticPool]] = Field(default=None, alias='staticPools')


class SNssaiUpfInfo(NFVCLBaseModel):
    s_nssai: Snssai = Field(..., alias='sNssai')
    dnn_upf_info_list: List[DnnUpfInfoListItem] = Field(..., alias='dnnUpfInfoList')


class Interface(NFVCLBaseModel):
    interface_type: str = Field(..., alias='interfaceType')
    endpoints: List[str]
    network_instances: List[str] = Field(..., alias='networkInstances')


class Upf(NFVCLBaseModel):
    type: Literal['UPF']
    node_id: str = Field(..., alias='nodeID')
    addr: str
    s_nssai_upf_infos: List[SNssaiUpfInfo] = Field(..., alias='sNssaiUpfInfos')
    interfaces: List[Interface]


Node = Annotated[Union[GNb, Upf], Field(discriminator='type')]


class UpNodes(RootModel):
    root: Dict[str, Node]


class Link(NFVCLBaseModel):
    a: str = Field(..., alias='A')
    b: str = Field(..., alias='B')


class UserplaneInformation(NFVCLBaseModel):
    up_nodes: UpNodes = Field(..., alias='upNodes')
    links: List[Link]


class T3591(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3592(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class SmfConfig(NFVCLBaseModel):
    smf_name: str = Field(..., alias='smfName')
    snssai_infos: List[SnssaiInfo] = Field(..., alias='snssaiInfos')
    plmn_list: List[PlmnId] = Field(..., alias='plmnList')
    userplane_information: UserplaneInformation = Field(
        ..., alias='userplaneInformation'
    )
    locality: str
    t3591: T3591
    t3592: T3592


class TopologyItem(NFVCLBaseModel):
    a: str = Field(..., alias='A')
    b: str = Field(..., alias='B')


class SpecificPathItem(NFVCLBaseModel):
    dest: str
    path: List[str]


class Ue(NFVCLBaseModel):
    members: List[str]
    topology: List[TopologyItem]
    specific_path: List[SpecificPathItem] = Field(..., alias='specificPath')


class UeRoutingInfo(RootModel):
    root: Dict[str, Ue]


class ConfigurationSmf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    ue_routing_info: Optional[UeRoutingInfo] = Field(default=None, alias='ueRoutingInfo')
    smf_configuration: SmfConfig = Field(None, alias='configuration')
    logger: Logger = Field(default=None, alias='logger')


class Smf1(NFVCLBaseModel):
    configuration: ConfigurationSmf = Field(default=None, alias='configuration')


class Free5gcSmf(NFVCLBaseModel):
    smf: Smf1


############################################### AMF ##################################################

class PlmnId(NFVCLBaseModel):
    mcc: str
    mnc: str


class ServedGuamiListItem(NFVCLBaseModel):
    plmn_id: PlmnId = Field(..., alias='plmnId')
    amf_id: str = Field(..., alias='amfId')


class SupportTaiListItem(NFVCLBaseModel):
    plmn_id: PlmnId = Field(..., alias='plmnId')
    tac: str

    @field_validator('tac')
    def field_checker(cls, v):
        if len(v) <= 6:
            v = v.zfill(6)
            ok = ok_regex.search(v) is not None
            if ok:
                return v
        raise Exception("Slice must be in range 000000~FFFFFF")


class PlmnSupportListItem(NFVCLBaseModel):
    plmn_id: PlmnId = Field(..., alias='plmnId')
    snssai_list: List[Snssai] = Field(..., alias='snssaiList')


class Security(NFVCLBaseModel):
    integrity_order: List[str] = Field(..., alias='integrityOrder')
    ciphering_order: List[str] = Field(..., alias='cipheringOrder')


class NetworkName(NFVCLBaseModel):
    full: str
    short: str


class MobilityRestrictionList(NFVCLBaseModel):
    enable: bool


class MaskedImeisv(NFVCLBaseModel):
    enable: bool


class RedirectionVoiceFallback(NFVCLBaseModel):
    enable: bool


class NgapIe(NFVCLBaseModel):
    mobility_restriction_list: MobilityRestrictionList = Field(
        ..., alias='mobilityRestrictionList'
    )
    masked_imeisv: MaskedImeisv = Field(..., alias='maskedIMEISV')
    redirection_voice_fallback: RedirectionVoiceFallback = Field(
        ..., alias='redirectionVoiceFallback'
    )


class NetworkFeatureSupport5Gs(NFVCLBaseModel):
    enable: bool
    length: int
    ims_vo_ps: int = Field(..., alias='imsVoPS')
    emc: int
    emf: int
    iwk_n26: int = Field(..., alias='iwkN26')
    mpsi: int
    emc_n3: int = Field(..., alias='emcN3')
    mcsi: int


class NasIe(NFVCLBaseModel):
    network_feature_support5_gs: NetworkFeatureSupport5Gs = Field(
        ..., alias='networkFeatureSupport5GS'
    )


class T3513(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3522(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3550(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3560(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3565(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class T3570(NFVCLBaseModel):
    enable: bool
    expire_time: str = Field(..., alias='expireTime')
    max_retry_times: int = Field(..., alias='maxRetryTimes')


class Sctp(NFVCLBaseModel):
    num_ostreams: int = Field(..., alias='numOstreams')
    max_instreams: int = Field(..., alias='maxInstreams')
    max_attempts: int = Field(..., alias='maxAttempts')
    max_init_timeout: int = Field(..., alias='maxInitTimeout')


class AmfConfig(NFVCLBaseModel):
    amf_name: str = Field(..., alias='amfName')
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    served_guami_list: List[ServedGuamiListItem] = Field(..., alias='servedGuamiList')
    support_tai_list: List[SupportTaiListItem] = Field(..., alias='supportTaiList')
    plmn_support_list: List[PlmnSupportListItem] = Field(..., alias='plmnSupportList')
    support_dnn_list: List[str] = Field(..., alias='supportDnnList')
    security: Security
    network_name: NetworkName = Field(..., alias='networkName')
    ngap_ie: NgapIe = Field(..., alias='ngapIE')
    nas_ie: NasIe = Field(..., alias='nasIE')
    t3502_value: int = Field(..., alias='t3502Value')
    t3512_value: int = Field(..., alias='t3512Value')
    non3gpp_dereg_timer_value: int = Field(..., alias='non3gppDeregTimerValue')
    t3513: T3513
    t3522: T3522
    t3550: T3550
    t3560: T3560
    t3565: T3565
    t3570: T3570
    locality: str
    sctp: Sctp
    default_ue_ctx_req: bool = Field(..., alias='defaultUECtxReq')


class ConfigurationAmf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    amf_configuration: AmfConfig = Field(None, alias='configuration')
    logger: Logger = Field(default=None, alias='logger')


# SerializableIPv4Address = Annotated[IPv4Address, PlainSerializer(lambda x: f'{x.exploded}', return_type=str, when_used='always')]
class Amf1(NFVCLBaseModel):
    configuration: ConfigurationAmf = Field(default=None, alias='configuration')


class Free5gcAmf(NFVCLBaseModel):
    amf: Amf1


########################################### NRF #########################################################
class OauthConfiguration(NFVCLBaseModel):
    oauth: bool = Field(..., alias='oauth')


class Db(NFVCLBaseModel):
    enabled: bool


class NrfConfiguration(NFVCLBaseModel):
    default_plmn_id: PlmnId = Field(..., alias='DefaultPlmnId')


class ConfigurationNrf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    oauthConfiguration: OauthConfiguration = Field(None, alias='oauthConfiguration')
    nrf_configuration: NrfConfiguration = Field(default=None, alias='configuration')
    logger: Logger


class Nrf1(NFVCLBaseModel):
    configuration: ConfigurationNrf = Field(default=None, alias='configuration')


class Free5gcNrf(NFVCLBaseModel):
    db: Db
    nrf: Nrf1


########################################### AUSF ########################################################

class AusfConfig(NFVCLBaseModel):
    plmn_support_list: List[PlmnId] = Field(..., alias='plmnSupportList')
    group_id: str = Field(..., alias='groupId')
    eap_aka_supi_imsi_prefix: bool = Field(..., alias='eapAkaSupiImsiPrefix')


class ConfigurationAusf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    ausf_configuration: AusfConfig = Field(None, alias='configuration')
    logger: Logger


class Ausf(NFVCLBaseModel):
    configuration: ConfigurationAusf = Field(default=None, alias='configuration')


class Free5gcAusf(NFVCLBaseModel):
    ausf: Ausf


############################################ N3IWF ######################################################


class PlmnidN3iwf(NFVCLBaseModel):
    mcc: str = Field(..., alias='MCC')
    mnc: str = Field(..., alias='MNC')


class GlobalN3Iwfid(NFVCLBaseModel):
    plmnid: PlmnidN3iwf = Field(..., alias='PLMNID')
    n3_iwfid: int = Field(..., alias='N3IWFID')


class SnssaiN3iwf(NFVCLBaseModel):
    sst: int = Field(..., alias='SST')
    sd: str = Field(..., alias='SD')

    @field_validator('sd')
    def field_checker(cls, v):
        if len(v) <= 6:
            v = v.zfill(6)
            ok = ok_regex.search(v) is not None
            if ok:
                return v
        raise Exception("Slice must be in range 000000~FFFFFF")


class TaiSliceSupportListItem(NFVCLBaseModel):
    snssai: SnssaiN3iwf = Field(..., alias='SNSSAI')


class BroadcastPlmnListItem(NFVCLBaseModel):
    plmnid: PlmnidN3iwf = Field(..., alias='PLMNID')
    tai_slice_support_list: List[TaiSliceSupportListItem] = Field(
        ..., alias='TAISliceSupportList'
    )


class SupportedTaListItem(NFVCLBaseModel):
    tac: str = Field(alias='TAC')
    broadcast_plmn_list: List[BroadcastPlmnListItem] = Field(
        ..., alias='BroadcastPLMNList'
    )

    @field_validator('tac')
    def field_checker(cls, v):
        if len(v) <= 6:
            v = v.zfill(6)
            ok = ok_regex.search(v) is not None
            if ok:
                return v
        raise Exception("Slice must be in range 000000~FFFFFF")


class N3IwfInformation(NFVCLBaseModel):
    global_n3_iwfid: GlobalN3Iwfid = Field(..., alias='GlobalN3IWFID')
    name: str = Field(..., alias='Name')
    supported_ta_list: List[SupportedTaListItem] = Field(..., alias='SupportedTAList')


class N3iwfConfiguration(NFVCLBaseModel):
    n3_iwf_information: N3IwfInformation = Field(..., alias='N3IWFInformation')
    ip_sec_interface_address: str = Field(..., alias='IPSecInterfaceAddress')
    ip_sec_interface_mark: int = Field(..., alias='IPSecInterfaceMark')
    nastcp_port: int = Field(..., alias='NASTCPPort')
    fqdn: str = Field(..., alias='FQDN')
    private_key: str = Field(..., alias='PrivateKey')
    certificate_authority: str = Field(..., alias='CertificateAuthority')
    certificate: str = Field(..., alias='Certificate')
    ueip_address_range: str = Field(..., alias='UEIPAddressRange')


class ConfigurationN3iwf(NFVCLBaseModel):
    ip_sec_interface_address: str = Field(..., alias='IPSecInterfaceAddress')
    n3iwf_configuration: N3iwfConfiguration = Field(None, alias='configuration')
    logger: Logger


class N3iwf(NFVCLBaseModel):
    configuration: ConfigurationN3iwf = Field(None, alias='configuration')


class Free5gcN3iwf(NFVCLBaseModel):
    n3iwf: N3iwf


################################################ NSSF ######################################################

class SupportedNssaiInPlmnListItem(NFVCLBaseModel):
    plmn_id: PlmnId = Field(..., alias='plmnId')
    supported_snssai_list: List[Snssai] = Field(
        ..., alias='supportedSnssaiList'
    )


class Tai(NFVCLBaseModel):
    plmn_id: PlmnId = Field(..., alias='plmnId')
    tac: str

    @field_validator('tac')
    def field_checker(cls, v):
        if len(v) <= 6:
            v = v.zfill(6)
            ok = ok_regex.search(v) is not None
            if ok:
                return v
        raise Exception("Slice must be in range 000000~FFFFFF")


class SupportedNssaiAvailabilityDatum(NFVCLBaseModel):
    tai: Tai
    supported_snssai_list: List[Snssai] = Field(
        ..., alias='supportedSnssaiList'
    )


class AmfListItem(NFVCLBaseModel):
    nf_id: str = Field(..., alias='nfId')
    supported_nssai_availability_data: List[SupportedNssaiAvailabilityDatum] = Field(
        ..., alias='supportedNssaiAvailabilityData'
    )


class RestrictedSnssaiListItem(NFVCLBaseModel):
    home_plmn_id: PlmnId = Field(..., alias='homePlmnId')
    s_nssai_list: List[Snssai] = Field(..., alias='sNssaiList')


class TaListItem(NFVCLBaseModel):
    tai: Tai
    access_type: str = Field(..., alias='accessType')
    supported_snssai_list: List[Snssai] = Field(
        ..., alias='supportedSnssaiList'
    )
    restricted_snssai_list: Optional[List[RestrictedSnssaiListItem]] = Field(
        None, alias='restrictedSnssaiList'
    )


class NsiInformationListItem(NFVCLBaseModel):
    nrf_id: str = Field("http://nrf-nrrf:8000/nnrf-nfm/v1/nf-instances", alias='nrfId')
    nsi_id: int = Field(..., alias='nsiId')


class NsiListItem(NFVCLBaseModel):
    snssai: Snssai
    nsi_information_list: List[NsiInformationListItem] = Field(
        ..., alias='nsiInformationList'
    )


class AmfSetListItem(NFVCLBaseModel):
    amf_set_id: int = Field(..., alias='amfSetId')
    amf_list: Optional[List[str]] = Field(None, alias='amfList')
    nrf_amf_set: str = Field(..., alias='nrfAmfSet')
    supported_nssai_availability_data: List[SupportedNssaiAvailabilityDatum] = Field(
        ..., alias='supportedNssaiAvailabilityData'
    )


class MappingOfSnssaiItem(NFVCLBaseModel):
    serving_snssai: Snssai = Field(..., alias='servingSnssai')
    home_snssai: Snssai = Field(..., alias='homeSnssai')


class MappingListFromPlmnItem(NFVCLBaseModel):
    operator_name: str = Field(..., alias='operatorName')
    home_plmn_id: PlmnId = Field(..., alias='homePlmnId')
    mapping_of_snssai: List[MappingOfSnssaiItem] = Field(..., alias='mappingOfSnssai')


class NssfConfiguration(NFVCLBaseModel):
    nssf_name: str = Field(..., alias='nssfName')
    supported_plmn_list: List[PlmnId] = Field(
        ..., alias='supportedPlmnList'
    )
    supported_nssai_in_plmn_list: List[SupportedNssaiInPlmnListItem] = Field(
        ..., alias='supportedNssaiInPlmnList'
    )
    nsi_list: List[NsiListItem] = Field(..., alias='nsiList')
    amf_set_list: List[AmfSetListItem] = Field(..., alias='amfSetList')
    amf_list: Optional[List[AmfListItem]] = Field(None, alias='amfList')
    ta_list: List[TaListItem] = Field(..., alias='taList')
    mapping_list_from_plmn: Optional[List[MappingListFromPlmnItem]] = Field(
        None, alias='mappingListFromPlmn'
    )


class ConfigurationNssf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    nssf_configuration: NssfConfiguration = Field(None, alias='configuration')
    logger: Logger


class Nssf(NFVCLBaseModel):
    configuration: ConfigurationNssf = Field(None, alias='configuration')


class Free5gcNssf(NFVCLBaseModel):
    nssf: Nssf


################################################ PCF ######################################################

class ServiceListItem(NFVCLBaseModel):
    service_name: str = Field(..., alias='serviceName')
    supp_feat: Optional[str] = Field(None, alias='suppFeat')


class PcfConfiguration(NFVCLBaseModel):
    pcf_name: str = Field(..., alias='pcfName')
    time_format: str = Field(..., alias='timeFormat')
    default_bdt_ref_id: str = Field(..., alias='defaultBdtRefId')
    locality: str


class ConfigurationPcf(NFVCLBaseModel):
    service_list: List[ServiceListItem] = Field(..., alias='serviceList')
    pcf_configuration: PcfConfiguration = Field(None, alias='configuration')
    logger: Logger


class Pcf(NFVCLBaseModel):
    configuration: ConfigurationPcf = Field(None, alias='configuration')


class Free5gcPcf(NFVCLBaseModel):
    pcf: Pcf


################################################ UDM ######################################################

class SuciProfileItem(NFVCLBaseModel):
    protection_scheme: int = Field(..., alias='ProtectionScheme')
    private_key: str = Field(..., alias='PrivateKey')
    public_key: str = Field(..., alias='PublicKey')


class UdmConfiguration(NFVCLBaseModel):
    suci_profile: List[SuciProfileItem] = Field(..., alias='SuciProfile')


class ConfigurationUdm(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')
    udm_configuration: UdmConfiguration = Field(None, alias='configuration')
    logger: Logger


class Udm(NFVCLBaseModel):
    configuration: ConfigurationUdm = Field(None, alias='configuration')


class Free5gcUdm(NFVCLBaseModel):
    udm: Udm


################################################ UDR ######################################################


class UdrConfiguration(NFVCLBaseModel):
    pass


class ConfigurationUdr(NFVCLBaseModel):
    service_name_list: Optional[List[str]] = Field(default_factory=list, alias='serviceNameList')
    udr_configuration: Optional[UdrConfiguration] = Field(default=None, alias='serviceNameList')
    logger: Logger


class Udr(NFVCLBaseModel):
    configuration: ConfigurationUdr = Field(None, alias='configuration')


class Free5gcUdr(NFVCLBaseModel):
    udr: Udr


################################################ CHF ######################################################

class ConfigurationChf(NFVCLBaseModel):
    service_name_list: List[str] = Field(..., alias='serviceNameList')


class Chf(NFVCLBaseModel):
    configuration: ConfigurationChf = Field(None, alias='configuration')


class Free5gcChf(NFVCLBaseModel):
    chf: Chf


################################################ NEF ######################################################


class ConfigurationNef(NFVCLBaseModel):
    service_list: List[ServiceListItem] = Field(..., alias='serviceList')


class Nef(NFVCLBaseModel):
    configuration: ConfigurationNef
    logger: Logger


class Free5gcNef(NFVCLBaseModel):
    nef: Nef


################################################ API ######################################################

class Free5gcLogin(NFVCLBaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class PermanentKey(NFVCLBaseModel):
    permanent_key_value: str = Field(..., alias='permanentKeyValue')
    encryption_key: Optional[int] = Field(0, alias='encryptionKey')
    encryption_algorithm: Optional[int] = Field(0, alias='encryptionAlgorithm')


class Op(NFVCLBaseModel):
    op_value: str = Field(..., alias='opValue')
    encryption_key: int = Field(..., alias='encryptionKey')
    encryption_algorithm: int = Field(..., alias='encryptionAlgorithm')


class Milenage(NFVCLBaseModel):
    op: Op


class Opc(NFVCLBaseModel):
    opc_value: str = Field(..., alias='opcValue')
    encryption_key: int = Field(..., alias='encryptionKey')
    encryption_algorithm: int = Field(..., alias='encryptionAlgorithm')


class AuthenticationSubscription(NFVCLBaseModel):
    authentication_method: str = Field(..., alias='authenticationMethod')
    sequence_number: str = Field(..., alias='sequenceNumber')
    authentication_management_field: str = Field(
        ..., alias='authenticationManagementField'
    )
    permanent_key: PermanentKey = Field(..., alias='permanentKey')
    milenage: Milenage
    opc: Opc


class SubscribedUeAmbr(NFVCLBaseModel):
    uplink: str
    downlink: str


class Nssai(NFVCLBaseModel):
    default_single_nssais: List[Snssai] = Field(
        ..., alias='defaultSingleNssais'
    )
    single_nssais: List[Snssai] = Field(..., alias='singleNssais')


class AccessAndMobilitySubscriptionData(NFVCLBaseModel):
    gpsis: List[str]
    subscribed_ue_ambr: SubscribedUeAmbr = Field(..., alias='subscribedUeAmbr')
    nssai: Nssai


class PduSessionTypes(NFVCLBaseModel):
    default_session_type: Optional[str] = Field("IPV4", alias='defaultSessionType')
    allowed_session_types: Optional[List[str]] = Field(["IPV4"], alias='allowedSessionTypes')


class SscModes(NFVCLBaseModel):
    default_ssc_mode: Optional[str] = Field("SSC_MODE_1", alias='defaultSscMode')
    allowed_ssc_modes: Optional[List[str]] = Field(["SSC_MODE_2", "SSC_MODE_3"], alias='allowedSscModes')


class Arp(NFVCLBaseModel):
    priority_level: int = Field(8, alias='priorityLevel')
    preempt_cap: str = Field("", alias='preemptCap')
    preempt_vuln: str = Field("", alias='preemptVuln')


class Field5gQosProfile(NFVCLBaseModel):
    field_5qi: int = Field(..., alias='5qi')
    arp: Optional[Arp] = Field(default_factory=Arp, alias='arp')
    priority_level: int = Field(8, alias='priorityLevel')


class SessionAmbr(NFVCLBaseModel):
    uplink: str
    downlink: str


class DnnInfoRoot(NFVCLBaseModel):
    pdu_session_types: Optional[PduSessionTypes] = Field(default_factory=PduSessionTypes, alias='pduSessionTypes')
    ssc_modes: Optional[SscModes] = Field(default_factory=SscModes, alias='sscModes')
    field_5g_qos_profile: Field5gQosProfile = Field(..., alias='5gQosProfile')
    session_ambr: SessionAmbr = Field(..., alias='sessionAmbr')
    static_ip_address: Optional[List] = Field(default_factory=list, alias='staticIpAddress')


class DnnConfigurations(RootModel):
    root: Dict[str, DnnInfoRoot]


class SessionManagementSubscriptionDatum(NFVCLBaseModel):
    single_nssai: Snssai = Field(..., alias='singleNssai')
    dnn_configurations: DnnConfigurations = Field(..., alias='dnnConfigurations')


class DnnInfoApi(NFVCLBaseModel):
    dnn: str


class SliceDnn(NFVCLBaseModel):
    dnn_infos: List[DnnInfoApi] = Field(..., alias='dnnInfos')


class SubscribedSnssaiInfos(RootModel):
    root: Dict[str, SliceDnn]


class SmfSelectionSubscriptionData(NFVCLBaseModel):
    subscribed_snssai_infos: SubscribedSnssaiInfos = Field(
        ..., alias='subscribedSnssaiInfos'
    )


class AmPolicyData(NFVCLBaseModel):
    subsc_cats: Optional[List[str]] = Field(["free5gc"], alias='subscCats')


class SmPolicyDnnData(RootModel):
    root: Dict[str, DnnInfoApi]


class SlicePolicy(NFVCLBaseModel):
    snssai: Snssai
    sm_policy_dnn_data: SmPolicyDnnData = Field(..., alias='smPolicyDnnData')


class SmPolicySnssaiData(RootModel):
    root: Dict[str, SlicePolicy]


class SmPolicyData(NFVCLBaseModel):
    sm_policy_snssai_data: SmPolicySnssaiData = Field(..., alias='smPolicySnssaiData')


class FlowRule(NFVCLBaseModel):
    filter: Optional[str] = Field("1.1.1.1/32", alias='filter')
    precedence: Optional[int] = Field(128, alias='precedence')
    snssai: str
    dnn: str
    qos_ref: int = Field(..., alias='qosRef')


class QosFlow(NFVCLBaseModel):
    snssai: str
    dnn: str
    qos_ref: int = Field(..., alias='qosRef')
    field_5qi: Optional[int] = Field(8, alias='5qi')
    mbr_ul: Optional[str] = Field("208 Mbps", alias='mbrUL')
    mbr_dl: Optional[str] = Field("208 Mbps", alias='mbrDL')
    gbr_ul: Optional[str] = Field("108 Mbps", alias='gbrUL')
    gbr_dl: Optional[str] = Field("108 Mbps", alias='gbrDL')


class ChargingData(NFVCLBaseModel):
    snssai: str
    dnn: Optional[str] = Field("", alias='dnn')
    filter: Optional[str] = Field("", alias='filter')
    charging_method: Optional[str] = Field("Offline", alias='chargingMethod')
    quota: Optional[str] = Field("10000", alias='quota')
    unit_cost: Optional[str] = Field("1", alias='unitCost')
    qos_ref: Optional[int] = Field(..., alias='qosRef')


class Free5gcSubScriber(NFVCLBaseModel):
    user_number: Optional[int] = Field(None, alias='userNumber')
    plmn_id: Optional[str] = Field(None, alias='plmnID')
    ue_id: Optional[str] = Field(None, alias='ueId')
    authentication_subscription: Optional[AuthenticationSubscription] = Field(None, alias='AuthenticationSubscription')
    access_and_mobility_subscription_data: Optional[AccessAndMobilitySubscriptionData] = Field(None, alias='AccessAndMobilitySubscriptionData')
    session_management_subscription_data: Optional[List[SessionManagementSubscriptionDatum]] = Field(None, alias='SessionManagementSubscriptionData')
    smf_selection_subscription_data: Optional[SmfSelectionSubscriptionData] = Field(None, alias='SmfSelectionSubscriptionData')
    am_policy_data: Optional[AmPolicyData] = Field(default_factory=AmPolicyData, alias='AmPolicyData')
    sm_policy_data: Optional[SmPolicyData] = Field(None, alias='SmPolicyData')
    flow_rules: Optional[List[FlowRule]] = Field(None, alias='FlowRules')
    qos_flows: Optional[List[QosFlow]] = Field(None, alias='QosFlows')
    charging_datas: Optional[List[ChargingData]] = Field(default_factory=List, alias='ChargingDatas')

    def clear_value(self):
        self.access_and_mobility_subscription_data.nssai.default_single_nssais.clear()
        self.access_and_mobility_subscription_data.nssai.single_nssais.clear()
        self.session_management_subscription_data.clear()
        self.smf_selection_subscription_data.subscribed_snssai_infos.root.clear()
        self.sm_policy_data.sm_policy_snssai_data.root.clear()
        self.flow_rules.clear()
        self.qos_flows.clear()
        self.charging_datas.clear()

    def update_subscriber_config(self, ue_id: str, current_config: Create5gModel, gpsi: str = None):
        self.clear_value()
        qosRef = 1
        self.plmn_id = current_config.config.plmn
        for subscriber in current_config.config.subscribers:
            if ue_id == subscriber.imsi:
                if gpsi:
                    self.access_and_mobility_subscription_data.gpsis.clear()
                    self.access_and_mobility_subscription_data.gpsis.append(f"msisdn-{gpsi}")
                self.ue_id = f"imsi-{subscriber.imsi}"
                self.authentication_subscription.authentication_method = subscriber.authenticationMethod
                self.authentication_subscription.opc.opc_value = subscriber.opc
                self.authentication_subscription.permanent_key.permanent_key_value = subscriber.k

                for _slice in subscriber.snssai:
                    for snssai in current_config.config.sliceProfiles:
                        if snssai.sliceId == _slice.sliceId and snssai.sliceType == _slice.sliceType:
                            temp_slice = Snssai(
                                sst=SstConvertion.to_int(snssai.sliceType),
                                sd=snssai.sliceId
                            )

                            self.access_and_mobility_subscription_data.nssai.default_single_nssais.append(temp_slice)
                            smsd = SessionManagementSubscriptionDatum(
                                single_nssai=temp_slice,
                                dnn_configurations=DnnConfigurations.model_validate({})
                            )

                            self.sm_policy_data.sm_policy_snssai_data.root[f"0{temp_slice.sst}{snssai.sliceId}"] = SlicePolicy(
                                snssai=temp_slice,
                                sm_policy_dnn_data=SmPolicyDnnData.model_validate({})
                            )

                            self.smf_selection_subscription_data.subscribed_snssai_infos.root[f"0{temp_slice.sst}{snssai.sliceId}"] = SliceDnn(dnn_infos=[])

                            for dnn_slice in snssai.dnnList:
                                for dnn in current_config.config.network_endpoints.data_nets:
                                    if dnn_slice == dnn.dnn:
                                        # flowr = FlowRule(
                                        #     snssai=f"0{temp_slice.sst}{snssai.sliceId}",
                                        #     dnn=dnn.dnn,
                                        #     qos_ref=qosRef
                                        # )
                                        #
                                        # qs = QosFlow(
                                        #     snssai=f"0{temp_slice.sst}{snssai.sliceId}",
                                        #     dnn=dnn.dnn,
                                        #     qos_ref=qosRef
                                        # )

                                        # cd = ChargingData(
                                        #     snssai=f"0{temp_slice.sst}{snssai.sliceId}",
                                        #     qos_ref=qosRef
                                        # )

                                        smsd.dnn_configurations.root[dnn.dnn] = DnnInfoRoot(
                                            field_5g_qos_profile=Field5gQosProfile(
                                                field_5qi=int(snssai.profileParams.pduSessions[0].flows[0].qi)
                                            ),
                                            session_ambr=SessionAmbr(
                                                uplink=snssai.profileParams.sliceAmbr,
                                                downlink=snssai.profileParams.sliceAmbr
                                            ),
                                        )
                                        self.smf_selection_subscription_data.subscribed_snssai_infos.root[f"0{temp_slice.sst}{snssai.sliceId}"].dnn_infos.append(DnnInfoApi(dnn=dnn.dnn))
                                        self.sm_policy_data.sm_policy_snssai_data.root[f"0{temp_slice.sst}{snssai.sliceId}"].sm_policy_dnn_data.root[dnn.dnn] = DnnInfoApi(dnn=dnn.dnn)
                                        # self.flow_rules.append(flowr)
                                        # self.qos_flows.append(qs)
                                        # self.charging_datas.append(cd)
                                        qosRef = qosRef + 1

                            self.session_management_subscription_data.append(smsd)
