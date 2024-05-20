====================
Topology description
====================

The Topology is the representation of the real topology on witch the NVFCL is working.

Everything that is contained in the Topology is used by the NFVCL to manage the lifecycle of Blueprints.

For example, when a Blueprint is deploying VMs, the VIM to be used is identified using the VIM data saved in the Topology.

.. image:: ../../images/blueprint/NVFCL-diagrams-BlueprintV1vsV2.drawio.svg
  :width: 400
  :alt: Flavor
  :align: center

As you can see from the picture, the topology information is modified by user's requests.

VIM list
########
The VIM is the one that is offering the possibility to deploy VMs to the NFVCL. This functionality is used from Blueprints
to deploy what it is requested by the user see :doc:`../blueprints/blueprint` (For example, a K8S cluster with 1 Controller
and 2 Workers for a total of 3 VMs).

We can have a list of VIMs associated to an area, in this way, the user can select in witch area the Blueprint will be deployed.
In case of multiple VIM for the same area, the first one is used.

K8S list
########
This is a list containing all the K8S cluster that can be used to deploy Helm Chart by Blueprints. As for the VIM list,
every K8S cluster is associated to an area and the user can select the one to use. In case of multiple clusters for an area,
the first one is used.

Net List
########
The network list is used to keep track of the network present in VIMs. Network can be added manually, if already present.
Networks can be also added and created by a Blueprint to this list, if needed.

Metric Server List
##################
This list is containing Prometheus instances that can be used to configure metrics exporters on Blueprint Resources.

Physical Device List
####################
TO BE COMPLETED. PDUs? Routers?
