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
