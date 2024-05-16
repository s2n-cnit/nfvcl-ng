====================
Blueprint
====================
The NFVCL is deploying ecosystems instances using Blueprints. A network ecosystem is meant to be a complete functional
network environment, such as a 5G system, an overlay system for network cybersecurity or a simple application service
mesh.

Blueprint System
+++++++++++++++++
Here will be described how the blueprint system (v2) is working. Blue V1 is NO more supported.

* Providers
* Configurators
* ...

Blueprint List
++++++++++++++

.. list-table:: Blueprint list
   :widths: 25 50 50 25
   :header-rows: 1

   * - Blueprint name
     - Type
     - Requirements
     - Blue Version
   * - :doc:`k8s/k8s_blue_index`
     - Kubernetes cluster
     - VIM(s) for VMs deployment
     - 2
   * - :doc:`free5gc/free5gc_blue_index`
     - 5G Core
     - K8s cluster onboarded in OSM + VIM
     - 1
   * - :doc:`5gcores/openairinterface/openairinterface_blue_index`
     - :doc:`5gcores/5gcore_blue_index`
     - K8s in topology + VIM
     - 2
   * - :doc:`5gcores/sdcore/sdcore_blue_index`
     - :doc:`5gcores/5gcore_blue_index`
     - K8s in topology + VIM
     - 2
   * - :doc:`vyos/vyos_blue_index`
     - Virtual Router
     - VIM
     - 2
   * - :doc:`ueransim/ueransim_blue_index`
     - gNodeB and UE emulator
     - VIM
     - 2

Blueprint LCM Management
++++++++++++++++++++++++
This section describes how the NFVCL user can use the Blueprint system to deploy, manage and destroy Blueprints.
The specific guide for APIs is found in the Blueprint dedicated page and in the NFVCL API swagger.

Blueprint creation
******************
The deployment of a Blueprint can result into the deployment of one or more VM/Helm-Chart.
To deploy VMs a VIM is required to be present in the Topology, while, for the deployment of a Helm Chart a K8S cluster is
needed in the Topology.
The K8S cluster can be deployed on VMs using the dedicated Blueprint (K8S) or can be added as external (already existing)
cluster to the topology.

To instantiate a blueprint it is sufficient to call a POST API, each blueprint has the dedicated call for its creation.

Blueprint day 2 operation
*************************
Some operations can be performed after the blueprint has been created/deployed, these actions include reconfiguration of
the blueprint (change the config of a VM) or the deployment of an new VM/Helm-Chart (like the addition of a VM to the blueprint)

Blueprint deletion
******************
To remove a Blueprint it should be only needed to call the DELETE call with the target ID.
