from typing import Optional

from nfvcl.models.blueprint_ng.core5g.common import SstConvertion, SubDataNets
from nfvcl.models.blueprint_ng.core5g.OAI_Models import Snssai, Baseconfig, Dnn, Upfconfig, \
    SNssaiUpfInfoListItem, DnnItem, Coreconfig, ServedGuamiListItem, OaiSmf, HostAliase, UpfAvailable, \
    LocalSubscriptionInfo, QosProfile, SNssaiSmfInfoListItem, PlmnSupportListItem


def add_snssai(config: Baseconfig, slice_id: str, slice_type: str) -> Snssai:
    """
    Add new "snssai" to OAI values configuration.
    :param config: config to add snssai to.
    :param slice_id: slice id of snssai to add.
    :param slice_type: slice type of snssai to add.
    :return: new snassai otherwise raise an error.
    """
    new_snssais = Snssai(
        sst=SstConvertion.to_int(slice_type),
        sd=slice_id.zfill(6)
    )
    if new_snssais not in config.snssais:
        config.snssais.append(new_snssais)
        return new_snssais
    raise ValueError(f"Add failed, slice {slice_id} already exist")


def del_snssai(config: Baseconfig, slice_id: str) -> Snssai:
    """
    Delete "snssai" from OAI values configuration.
    :param config: config to remove snssai from.
    :param slice_id: slice id of the snssai to delete.
    :return: deleted snssai otherwise raise an error.
    """
    for snssai in config.snssais:
        if snssai.sd == slice_id:
            config.snssais.remove(snssai)
            return snssai
    raise ValueError(f"Delete failed, slice {slice_id} doesnt exist")


def add_dnn_dnns(config: Baseconfig, dnn_name: str, dnn_cidr: str) -> Optional[Dnn]:
    """
    Add "dnn" to OAI values configuration.
    :param config: config to add dnn.
    :param dnn_name: name of dnn.
    :param dnn_cidr: cidr of dnn.
    :return: new dnn otherwise None.
    """
    new_dnn = Dnn(
        dnn=dnn_name,
        ipv4_subnet=dnn_cidr
    )
    if new_dnn not in config.dnns:
        config.dnns.append(new_dnn)
        return new_dnn
    return None


def del_dnn_dnns(config: Baseconfig, dnn_to_remove: str) -> bool:
    """
    Delete "dnn" to OAI values configuration.
    :param config: config to remove dnn from.
    :param dnn_to_remove: dnn to remove.
    :return: True if removed, False otherwise.
    """
    for dnn in config.dnns:
        if dnn.dnn == dnn_to_remove:
            config.dnns.remove(dnn)
            return True
    return False


def create_snssai_upf_info_list_item(config: Upfconfig, nssai: Snssai) -> Optional[SNssaiUpfInfoListItem]:
    """
    Add new item to OAI values configuration "snssai_upf_info_list".
    :param config: config to add the item to.
    :param nssai: snssai of the item.
    :return: new item, if it already exists None.
    """
    new_s_nssai_item = SNssaiUpfInfoListItem(
        sNssai=nssai,
        dnnUpfInfoList=[]
    )
    if new_s_nssai_item not in config.upf.upf_info.sNssaiUpfInfoList:
        config.upf.upf_info.sNssaiUpfInfoList.append(new_s_nssai_item)
        return new_s_nssai_item
    return None


def destroy_snssai_upf_info_list_item(config: Upfconfig, slice_id: str) -> bool:
    """
    Delete item from values configuration "snssai_upf_info_list".
    :param config: config to delete the item from.
    :param slice_id: slice id of nssai.
    :return: True if the item was successfully deleted, otherwise False.
    """
    for item in config.upf.upf_info.sNssaiUpfInfoList:
        if item.sNssai.sd == slice_id:
            config.upf.upf_info.sNssaiUpfInfoList.remove(item)
            return True
    return False


def add_dnn_snssai_upf_info_list_item(config: Upfconfig, snssai: Snssai, dnn: DnnItem) -> Optional[bool]:
    """
    Add item to OAI values configuration "dnn_snssai_upf_info_list", if "snssai_upf_info_list" doesn't exist
    it will be created and then item added.
    :param config: config to add the item to.
    :param snssai: snssai of the item.
    :param dnn: dnn of the item.
    :return: True if the item was successfully added, otherwise None.
    """
    for item in config.upf.upf_info.sNssaiUpfInfoList:
        if item.sNssai.sd == snssai.sd:
            if dnn not in item.dnnUpfInfoList:
                item.dnnUpfInfoList.append(dnn)
            return True
    create_snssai_upf_info_list_item(config, snssai)
    add_dnn_snssai_upf_info_list_item(config, snssai, dnn)


def add_served_guami_list_item(config: Coreconfig, mcc: str, mnc: str) -> Optional[ServedGuamiListItem]:
    """
    Add item to OAI values configuration "served_guami_list".
    :param config: config to add the item to.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :return: added item, otherwise None.
    """
    served_guami_list_item = ServedGuamiListItem(
        mcc=mcc,
        mnc=mnc,
        amf_region_id=mnc,
        amf_set_id=mcc,
        amf_pointer=mnc
    )
    if served_guami_list_item not in config.amf.served_guami_list:
        config.amf.served_guami_list.append(served_guami_list_item)
        return served_guami_list_item
    return None


def del_served_guami_list_item(config: Coreconfig, mcc: str, mnc: str) -> bool:
    """
    Delete item from OAI values configuration "served_guami_list".
    :param config: config to delete the item from.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :return: True if item was successfully deleted, otherwise False.
    """
    for item in config.amf.served_guami_list:
        if item.mcc == mcc and item.mnc == mnc:
            config.amf.served_guami_list.remove(item)
            return True
    return False


def add_host_aliases(config: OaiSmf, area_id: int, ip_upf: str) -> HostAliase:
    """
    Add new "host alias" to OAI SMF configuration.
    :param config: config to add host alias to.
    :param area_id: area id of upf.
    :param ip_upf: ip of upf.
    :return: new host alias, raise an error otherwise.
    """
    new_hostalias = HostAliase(
        ip=ip_upf,
        hostnames=f"oai-upf{area_id}"
    )
    if new_hostalias not in config.hostAliases:
        config.hostAliases.append(new_hostalias)
        return new_hostalias
    raise ValueError(f"Add failed, oai-upf{area_id} already exist")


def del_host_aliases(config: OaiSmf, area_id: int) -> bool:
    """
    Delete "host alias" from OAI SMF configuration.
    :param config: config to remove host alias from.
    :param area_id: area id of upf.
    :return: True if sucessfully delete host alias, otherwise raise an error.
    """
    for host in config.hostAliases:
        if host.hostnames == f"oai-upf{area_id}":
            config.hostAliases.remove(host)
            return True
    raise ValueError(f"Delete failed, oai-upf{area_id} doesnt exist")


def add_available_upf(config: Coreconfig, area_id: int) -> Optional[UpfAvailable]:
    """
    Add "available upf" to OAI values configuration.
    :param config: config to add available upf to.
    :param area_id: area id of upf.
    :return: new available upf, otherwise None.
    """
    new_upf_supported = UpfAvailable(
        host=f"oai-upf{area_id}"
    )
    if new_upf_supported not in config.smf.upfs:
        config.smf.upfs.append(new_upf_supported)
        return new_upf_supported
    return None


def del_available_upf(config: Coreconfig, area_id: int) -> bool:
    """
    Delete "available upf" from OAI values configuration.
    :param config: config to remove available upf from.
    :param area_id: area id of upf.
    :return: True if it was successfully deleted, otherwise False.
    """
    for upf in config.smf.upfs:
        if upf.host == f"oai-upf{area_id}":
            config.smf.upfs.remove(upf)
            return True
    return False


def add_local_subscription_info(config: Coreconfig, snnsai: Snssai, dnn: SubDataNets) -> Optional[LocalSubscriptionInfo]:
    """
    Add new "local_subscription_info" to OAI values configuration.
    :param config: config to add local_subscription_info to.
    :param snnsai: snnsai of local_subscription_info.
    :param dnn: dnn of local_subscription_info.
    :return: new local_subscription_info, otherwise None.
    """
    local_subscription_info = LocalSubscriptionInfo(
        single_nssai=snnsai,
        dnn=dnn.dnn,
        qos_profile=QosProfile(
            field_5qi=dnn.default5qi,
            session_ambr_ul=dnn.uplinkAmbr.replace(" ", ""),
            session_ambr_dl=dnn.downlinkAmbr.replace(" ", "")
        )
    )
    if local_subscription_info not in config.smf.local_subscription_infos:
        config.smf.local_subscription_infos.append(local_subscription_info)
        return local_subscription_info
    return None


def del_local_subscription_info(config: Coreconfig, slice_id: str, dnn: str) -> bool:
    """
    Delete "local_subscription_info" from OAI values configuration.
    :param config: config to delete local subscription info from.
    :param slice_id: slice id of snssai.
    :param dnn: dnn of local subscription info.
    :return: True if it was successfully deleted, False otherwise.
    """
    for info in config.smf.local_subscription_infos:
        if info.dnn == dnn and info.single_nssai.sd == slice_id:
            config.smf.local_subscription_infos.remove(info)
            return True
    return False


def create_snssai_smf_info_list(config: Coreconfig, nssai: Snssai) -> Optional[SNssaiSmfInfoListItem]:
    """
    Add new item to OAI values configuration "snssai_smf_info_list".
    :param config: config to add the item to.
    :param nssai: snssai of the item.
    :return: new item, if it already exists None.
    """
    snssai_smf_info_list_item = SNssaiSmfInfoListItem(
        sNssai=nssai,
        dnnSmfInfoList=[]
    )
    if snssai_smf_info_list_item not in config.smf.smf_info.sNssaiSmfInfoList:
        config.smf.smf_info.sNssaiSmfInfoList.append(snssai_smf_info_list_item)
        return snssai_smf_info_list_item
    return None


def destroy_snssai_smf_info_list_item(config: Coreconfig, slice_id: str) -> bool:
    """
    Delete item from values configuration "snssai_smf_info_list_item".
    :param config: config to delete the item from.
    :param slice_id: slice id of nssai.
    :return: True if the item was successfully deleted, otherwise False.
    """
    for item in config.smf.smf_info.sNssaiSmfInfoList:
        if item.sNssai.sd == slice_id:
            config.smf.smf_info.sNssaiSmfInfoList.remove(item)
            return True
    return False


def add_dnn_snssai_smf_info_list_item(config: Coreconfig, nssai: Snssai, dnn: DnnItem) -> Optional[bool]:
    """
    Add item to OAI values configuration "dnn_snssai_smf_info_list", if "snssai_smf_info_list" doesn't exist
    it will be created and then item added.
    :param config: config to add the item to.
    :param nssai: snssai of the item.
    :param dnn: dnn of the item.
    :return: True, if the item was successfully added, otherwise None.
    """
    for item in config.smf.smf_info.sNssaiSmfInfoList:
        if item.sNssai.sd == nssai.sd:
            if dnn not in item.dnnSmfInfoList:
                item.dnnSmfInfoList.append(dnn)
            return True
    create_snssai_smf_info_list(config, nssai)
    add_dnn_snssai_smf_info_list_item(config, nssai, dnn)


def create_plmn_list(config: Coreconfig, mcc: str, mnc: str, area_id: int) -> Optional[PlmnSupportListItem]:
    """
    Add new item to OAI values configuration "plmn_list".
    :param config: config to add the item to.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :param area_id: area id of the item.
    :return: new plmn_item, otherwise None.
    """
    plmn_item = PlmnSupportListItem(
        mnc=mnc,
        mcc=mcc,
        tac=area_id,
        nssai=[]
    )
    if plmn_item not in config.amf.plmn_support_list:
        config.amf.plmn_support_list.append(plmn_item)
        return plmn_item
    return None


def destroy_plmn_list(config: Coreconfig, mcc: str, mnc: str, area_id: int) -> bool:
    """
    Delete item from values configuration "plmn_list".
    :param config: config to delete the item from.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :param area_id: area id of the item.
    :return: True if the item was successfully deleted, otherwise False.
    """
    for item in config.amf.plmn_support_list:
        if item.mcc == mcc and item.mnc == mnc and item.tac == area_id:
            config.amf.plmn_support_list.remove(item)
            return True
    return False


def add_plmn_item(config: Coreconfig, mcc: str, mnc: str, area_id: int, nssai: Snssai) -> Optional[bool]:
    """
    Add item to OAI values configuration "plmn_list", if "plmn_list" doesn't exist
    it will be created and then item added.
    :param config: config to add the item to.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :param area_id: area id of the item.
    :param nssai: nssai of the item.
    :return: True if item was successfully added, otherwise None.
    """
    for item in config.amf.plmn_support_list:
        if item.mcc == mcc and item.mnc == mnc and item.tac == area_id:
            if nssai not in item.nssai:
                item.nssai.append(nssai)
            return True
    create_plmn_list(config, mcc, mnc, area_id)
    add_plmn_item(config, mcc, mnc, area_id, nssai)


def del_plmn_item(config: Coreconfig, mcc: str, mnc: str, area_id: int, nssai: Snssai) -> bool:
    """
    Delete item from OAI values configuration "plmn_list", if "plmn_list" it's empty
    it will be deleted.
    :param config: config to delete the item from.
    :param mcc: mcc of the item.
    :param mnc: mnc of the item.
    :param area_id: area id of the item.
    :param nssai: nssai of the item.
    :return: True if item was successfully deleted, otherwise False.
    """
    for item in config.amf.plmn_support_list:
        if item.mcc == mcc and item.mnc == mnc and item.tac == area_id and nssai in item.nssai:
            item.nssai.remove(nssai)
            if len(item.nssai) == 0:
                destroy_plmn_list(config, mcc, mnc, area_id)
            return True
    return False
