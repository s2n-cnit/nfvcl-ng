====================
Blueprint
====================

Blueprint creation
******************
The creation of a blueprint can result into the deployment of VDU, KDU and PDU. The combination of these last
elements strongly depends on the blueprint ecosystem, for example, the kubernetes blueprint result in one
or more VDUs: one is the cluster controller, and the others are workers (the number depends on the creation request).

To instantiate a blueprint it is sufficient to call a POST API, each blueprint has its dedicated call for creation.

Blueprint day 2 operation
*************************
Some operations can be performed after the blueprint has been instantiated, these actions include reconfiguration of
deployed unit (DU) or their increment.

Blueprint deletion
******************
