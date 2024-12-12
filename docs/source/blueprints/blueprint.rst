.. contents::

====================
Blueprint
====================
The NFVCL is deploying ecosystems instances using Blueprints. A network ecosystem is meant to be a complete functional
network environment, such as a 5G system, an overlay system for network cybersecurity or a simple application service
mesh.

.. image:: ../../images/blueprint/NVFCL-diagrams-BlueprintV1vsV2.drawio.svg
  :width: 400
  :alt: Flavor
  :align: center

Blueprint System
+++++++++++++++++
Starting from the top of the picture, we can see that everything that happens in the NFVCL is triggered by the user.
For the topology part, please refer to (:doc:`../topology/topology`).

The Blueprint Life Cycle Management (LCM) have a dedicated manager witch main scope is to load and save Blueprints from
the NFVCL database.

A Blueprint contains a lot of data that can be categorized in:

* Status: contains information of the status of resources (like the list of interfaces with the relative IP)
* Configurators: the list of configurators (status included) that are created and used by the Blueprint (Day0,Day2,DayN)
* Topology: the information of the topology in witch the Blueprint is deployed.

.. image:: ../../images/NVFCL-diagrams-General-Scheme.drawio.svg
  :width: 400
  :alt: Flavor
  :align: center

The code of a Blueprint class is the one managing how, and in witch order, Resources are generated. The Blueprint instance is
also managing Day2 operations like adding,updating and deleting a node from the blueprint instance.

The new Blueprint system abstract the concept of Provider, offering to the every type of Blueprint an uniform set of functions.
These functions are offering the tools for LCM of resources composing the specific instance of that type of blueprint.

Since a Blueprint can be composed of both VMs and K8S resources, the provider interaction is not limited to one,
but we can interact with several providers.

Flavors
*******
Flavors of a blueprint could be problematic, usually flavors for VMs are created on Blueprint creation or when adding nodes to
an existing Blueprint. It is not always possible to do this operation, depending on user permission.
In this case it is possible to use an existing flavor.
The scheme below summarize the behavior depending on the case.

.. image:: ../../images/blueprint/NVFCL-diagrams-Flavor-Management.drawio.svg
  :width: 400
  :alt: Flavor
  :align: center

Blueprint Type List
+++++++++++++++++++

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
     - K8s in topology + VIM
     - 2
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
   * - Ubuntu Blueprint
     - Creates a VM running Ubuntu 22/24
     - VIM
     - 2


Blueprint LCM Management
++++++++++++++++++++++++
This section describes how the NFVCL user can use the Blueprint system to deploy, manage and destroy Blueprints.
The specific guide for APIs is found in the Blueprint dedicated page and in the NFVCL API swagger.

Blueprint deployment/instantiation
**********************************
The deployment of a Blueprint can result into the deployment of one or more VM/Helm-Chart.
To deploy VMs a VIM is required to be present in the Topology, while, for the deployment of a Helm Chart a K8S cluster is
needed in the Topology.
The K8S cluster can be deployed on VMs using the dedicated Blueprint (K8S) or can be added as external (already existing)
cluster to the topology.

To instantiate a blueprint it is sufficient to call a POST API, each blueprint has the dedicated call for its creation.
**For further details** please see the specific Blueprint dedicated page.

Blueprint day 2 operation
*************************
Some operations can be performed after the blueprint has been created/deployed, these actions include reconfiguration of
the blueprint (change the config of a VM) or the deployment of an new VM/Helm-Chart (like the addition of a VM to the blueprint)

Blueprint deletion
******************
To remove a Blueprint it should be only needed to call the DELETE call with the target ID.

Blueprint instances
*******************
To retrieve a list of instantiated blueprints you can make a GET request to:

http://NFVCL_URL:5002/nfvcl/v2/api/blue/

To get a list that includes all the details of a Blueprint instance you can add the following query param:

http://NFVCL_URL:5002/nfvcl/v2/api/blue/?detailed=true
