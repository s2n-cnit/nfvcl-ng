from typing import List
from ..models import VyOSConfig, VyOSArea, VyOSRouterPortModel, VyOSSourceNATRule, VyOSDestNATRule
from ipaddress import IPv4Network

def check_interface_exists(interface_name: str, target_router_config: VyOSConfig) -> bool:
    """
    Check that an interface name exist in the blueprint endpoints (both management and data networks
    """
    router_interfaces = [target_router_config.network_endpoints.mgt.interface_name]
    for data_interface in target_router_config.network_endpoints.data_nets:
        router_interfaces.append(data_interface.interface_name)
    if not any(interface_name == interface for interface in router_interfaces):
        return False
    return True

def check_network_exists_in_router(target_network_addr: str, target_router_config: VyOSConfig) -> VyOSRouterPortModel:
    """

    """
    router_networks_list: List[VyOSRouterPortModel] = [target_router_config.network_endpoints.mgt]
    router_networks_list.extend(target_router_config.network_endpoints.data_nets)
    target_network = IPv4Network(target_network_addr)

    target_network = [router_network for router_network in router_networks_list if
                           router_network.network == target_network]

    if len(target_network)>0:
        return target_network[0]
    else:
        raise ValueError(
            "Error while looking for network {} in router {}: network NOT found".format(target_network_addr,target_router_config.name))

def check_rule_exists_in_router(rule_number: str, target_router_config: VyOSConfig) -> [VyOSSourceNATRule, VyOSDestNATRule]:
    """

    """
    to_return = [None, None]

    for snat_rule in target_router_config.snat_rules:
        if snat_rule.rule_number == rule_number:
            to_return[0] = snat_rule
    for dnat_rule in target_router_config.dnat_rules:
        if dnat_rule.rule_number == rule_number:
            to_return[1] = dnat_rule
    return to_return


def search_for_target_router_in_area(area_list: List[VyOSArea], target_area_id: int, target_router_name: str) -> [int, VyOSConfig]:
    """
    Looks for the target router inside each area in the areas list.

    @param area_list: the area list to search from

    @param target_area_id: the area to search for the router

    @param target_router_name: the router to search in the area

    @return the corresponding area and the target router if the router is present in the target area.
    """

    target_areas = [area_iterator for area_iterator in area_list if area_iterator.id == target_area_id]
    if len(target_areas) > 0:
        target_area = target_areas[0]
        target_router_configs = [router_iterator for router_iterator in target_area.config_list if
                                 router_iterator.name == target_router_name]
        if len(target_router_configs) > 0:
            target_router_config: VyOSConfig = target_router_configs[0]
        else:
            raise ValueError("Error while looking for the router in the area {}: {} router NOT found inside the area".format(target_area_id,target_router_name))
    else:
        raise ValueError("Error while looking for the area {}: area list does NOT contain that area".format(target_area_id))

    return [target_area, target_router_config]


def search_for_routers_in_area(area_list: List[VyOSArea], target_area_id: int) -> List[VyOSConfig]:
    """
    Looks for the target router inside each area in the areas list.

    @param area_list: the area list to work on

    @param target_area_id: the area to retrieve routers from.

    @return the corresponding area and the target router if the router is present in the target area.
    """

    target_areas = [area_iterator for area_iterator in area_list if area_iterator.id == target_area_id]
    if len(target_areas) > 0:
        target_area = target_areas[0]
        return target_area.config_list
    else:
        raise ValueError("Error while looking for the area {}: area list does NOT contain that area".
                         format(target_area_id))
