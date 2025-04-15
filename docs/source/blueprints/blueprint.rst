.. contents::

====================
Blueprint
====================
The NFVCL is deploying ecosystems instances using Blueprints. A network ecosystem is meant to be a complete functional
network environment, such as a 5G system, an overlay system for network cybersecurity or a simple application service
mesh.

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
Flavors are the technical specification of a VM in a Blueprint, using the right one can be problematic. Usually flavors for VMs are created on Blueprint creation or when adding nodes to
an existing Blueprint. It is not always possible to do this operation, depending on user permission on the VIM.
In this case it is possible to use an existing flavor.
The scheme below summarize the behavior depending on the case.

.. image:: ../../images/blueprint/NVFCL-diagrams-Flavor-Management.drawio.svg
  :width: 400
  :alt: Flavor
  :align: center

Blueprint Type List
+++++++++++++++++++
Here you find a list of all developed Blueprints, their type and the requirements for their deployment.

.. list-table:: Blueprint list
   :widths: 25 50 50
   :header-rows: 1

   * - Blueprint name
     - Type
     - Requirements
   * - :doc:`k8s/k8s_blue_index`
     - Kubernetes cluster
     - VIM(s) for VMs deployment
   * - :doc:`5gcores/free5gc/free5gc_blue_index`
     - :doc:`5gcores/5gcore_blue_index`
     - (K8s + VIM) in topology
   * - :doc:`5gcores/openairinterface/openairinterface_blue_index`
     - :doc:`5gcores/5gcore_blue_index`
     - (K8s + VIM) in topology
   * - :doc:`5gcores/sdcore/sdcore_blue_index`
     - :doc:`5gcores/5gcore_blue_index`
     - (K8s + VIM) in topology
   * - :doc:`vyos/vyos_blue_index`
     - Virtual Router
     - VIM
   * - :doc:`ueransim/ueransim_blue_index`
     - gNodeB and UE emulator
     - VIM
   * - Ubuntu Blueprint
     - Creates a VM running Ubuntu 22/24
     - VIM


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

Blueprint Destroy/Deletion
**************************
To remove a Blueprint it should be only needed to call the DELETE call with the target ID.

http://NFVCL_URL:5002/nfvcl/v2/api/blue/BLUE_ID

Blueprint Protection
********************
The protection of a blueprint can be used to prevent the deletion of a blueprint. It it a PATCH request:

http://NFVCL_URL:5002/nfvcl/v2/api/blue/protect/BLUE_ID

Blueprint instances
*******************
To retrieve a list of instantiated blueprints you can make a GET request to:

http://NFVCL_URL:5002/nfvcl/v2/api/blue/

To get a list that includes all the details of a Blueprint instance you can add the following query param:

http://NFVCL_URL:5002/nfvcl/v2/api/blue/?detailed=true

Blueprint Snapshots
+++++++++++++++++++
Snapshots are used to save the state of a Blueprint instance. The snapshot can be used to restore the state of the Blueprint, the way that the snapshot is restored is
performing every single operation that was performed on the Blueprint instance since its creation till the state at the snapshot creation.
**You can find all possible operations on the Swagger.**

Snapshot Creation
*************************
To create a snapshot of a Blueprint instance it is sufficient to call a POST API

http://192.168.12.42:5002/nfvcl/v2/api/snapshot/BLUE_ID?snapshot_name=TEST-ABC2

Snapshot Destroy/Deletion
*************************
To remove a snapshot it should be only needed to call the DELETE call with the target ID.

http://NFVCL_URL:5002/nfvcl/v2/api/snapshot/TEST-ABC2

