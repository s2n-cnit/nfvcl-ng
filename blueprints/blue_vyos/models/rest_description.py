ADD_SNAT_DESCRIPTION: str = "This method allow to add a source NAT rule to a specific router belonging to the specified" \
                            " blueprint. If the rule number is already present, the rule is overwritten." \
                            "See the schema for better details."
ADD_SNAT_SUMMARY: str = "Add SNAT rule to a vyos instance of the blueprint"
ADD_DNAT_DESCRIPTION: str = "This method allow to add a destination NAT rule to a specific router belonging to the " \
                            "specified blueprint. If the rule number is already present, the rule is overwritten." \
                            "See the schema for better details."
ADD_DNAT_SUMMARY: str = "Add DNAT rule to a vyos instance of the blueprint"
ADD_1TO1_NAT_DESCRIPTION: str = "This method allow to add a 1:1 NAT rule to a specific router belonging to the " \
                                "specified blueprint. This rule is a particular combination of source and destination" \
                                " NAT. This implies that a rule with the same rule_number will be added both for source" \
                                "and destination NAT. See the schema for better details."
ADD_1TO1_NAT_SUMMARY: str = "Add 1 to 1 NAT rule to a vyos instance of the blueprint"
DEL_NAT_DESCRIPTION: str = "This method remove a rule number. NB if a source NAT rule and a destination NAT rule are" \
                           "present at the same time WITH THE SAME RULE NUMBER, THEY ARE BOTH DELETED. In this way it is" \
                           "possible to delete in one step a 1 to 1 NAT. See the schema for better details."
DEL_NAT_SUMMARY: str = "Delete a NAT rule of a vyos instance of the blueprint"
GET_VYOS_BY_AREA_DESCRIPTION: str = ""
GET_VYOS_BY_AREA_SUMMARY: str = ""
ADD_FIR_DESCRIPTION: str = "This method allows to add a port, a network, an address or an interface group"
ADD_FIR_SUMMARY: str = "Add a group to a vyos instance of the blueprint"
ADD_FIR_RULE_DESCRIPTION: str = "This method allow to create a Firewall (the only mandatory parameter is the firewallname)" \
                                " in which it is possible to apply firewall rules to one or more VyOS interfaces that provide" \
                                " an action (example: accept, drop) to ports, addresses, networks, port groups, address groups" \
                                " or network groups (depending on the optional parameters that are set in the body of the call)." \
                                " It is possible to specify a VyOS default action, a protocol to which a rule can be applied" \
                                " (for example tcp, udp, all). In the body of the function, if a firewall rule is inserted, it is necessary to specify" \
                                " the var parameter (source or destination). When creating the firewall it is possible to set the “en_ping” parameter" \
                                " enable or disable. If it is set as enable, VyOS will respond to every ICMP request, unless there is a rule that provides" \
                                " for the rejection of ICMP echo requests. Finally, the “variable” parameter (local, i.e. the set of rules is applied to packets" \
                                " destined for this router, in, applied to packets forwarded on an incoming interface, or out, applied to packets forwarded" \
                                " on an outgoing interface) must be specified if you want to apply a firewall to an interface."
ADD_FIR_RULE_SUMMARY: str = "Add Firewall rule to a vyos instance of the blueprint"
