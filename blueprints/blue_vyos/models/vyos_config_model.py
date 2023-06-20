from typing import Optional, List
from pydantic import BaseModel, Field
from .vyos_router_network_endpoint_model import VyOSRouterNetworkEndpoints
from .vyos_vm_flavors_model import VMFlavors
from .vyos_nat_rules_model import VyOSDestNATRule, VyOSSourceNATRule


class VyOSConfig(BaseModel):
    version: Optional[str] = "1.00"
    name: Optional[str]
    nsd_name: Optional[str]
    nsd_id: Optional[str]
    network_endpoints: VyOSRouterNetworkEndpoints
    admin_username: str = Field(default='vyos')
    admin_password: str = Field(default='vyos')
    vyos_router_flavors: Optional[VMFlavors]
    snat_rules: Optional[List[VyOSSourceNATRule]]
    dnat_rules: Optional[List[VyOSDestNATRule]]

    def extend_snat_rules(self, list_to_append: List[VyOSSourceNATRule]):
        """
        Method to manage snat rule addiction
        @param list_to_append: the list of rule to be added at the Vyos configuration
        """
        if not self.snat_rules:
            self.snat_rules = []
        for rule_to_add in list_to_append:
            if rule_to_add in self.snat_rules:
                index = self.snat_rules.index(rule_to_add)
                #Overwrite the existing one
                self.snat_rules[index] = rule_to_add
            else:
                self.snat_rules.append(rule_to_add)

    def extend_dnat_rules(self, list_to_append: List[VyOSDestNATRule]):
        """
        Method to manage dnat rule addiction
        @param list_to_append: the list of rule to be added at the Vyos configuration
        """
        if not self.dnat_rules:
            self.dnat_rules = []
        for rule_to_add in list_to_append:
            if rule_to_add in self.dnat_rules:
                index = self.dnat_rules.index(rule_to_add)
                #Overwrite the existing one
                self.dnat_rules[index] = rule_to_add
            else:
                self.dnat_rules.append(rule_to_add)

    def remove_snat_rules(self, list_to_remove: List[VyOSSourceNATRule]):
        """
        Method to manage snat rule removal
        @param list_to_remove: the list of snat rule to be removed from the Vyos configuration
        """
        if not self.snat_rules:
            self.snat_rules = []
        for rule in list_to_remove:
            self.snat_rules.remove(rule)

    def remove_dnat_rules(self, list_to_remove: List[VyOSDestNATRule]):
        """
        Method to manage dnat rule removal
        @param list_to_remove: the list of dnat rule to be removed from the Vyos configuration
        """
        if not self.dnat_rules:
            self.dnat_rules = []
        for rule in list_to_remove:
            self.dnat_rules.remove(rule)