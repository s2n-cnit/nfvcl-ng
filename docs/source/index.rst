Home
====

.. note::

   This project is under active development.

The Network Resource Management offered by CNIT is called NFVCL and it is an open-source software[1] devoted to network-oriented meta-orchestration, specifically designed for zeroOps and continuous automation.
The NFVCL is deploying network ecosystem instances using Blueprints (Day-0 and Day-1), these network ecosystems can be composed by different components, such VMs or K8S pods, offering a service.
The deployment of a Blueprint can be done over a VIM and a Kubernetes cluster (some components may require to be VMs and others Containers). In detail, a network ecosystem is meant to be a complete functional network environment, such as a 5G system, an overlay system for network cybersecurity or a simple application service mesh.
Once a Blueprint instance has been deployed, the NFVCL is capable of managing Day-2 and Day-N operation, requested by the user, to the specific instance. The supported operations (Day-X) must be supported by the code of the specific Blueprint. In general, it can be said that the NFVCL is managing all the life-cycle of the Blueprint (LCM).

.. contents::

The installation procedure is described in the main `README <https://github.com/s2n-cnit/nfvcl-ng>`_.

The NFVCL is working through REST API calls, you can see every available API in the swagger offered by the NFVCL.
You can find the swagger at URL: http://NFVCL-IP:5002/docs

The NFVCL is deploying ecosystems instances using Blueprints. The deployment of a Blueprint can be done over a VIM and
a Kubernetes cluster (some components may require to be VMs and others Containers).
The Blueprint general description and list is available there :doc:`blueprints/blueprint`)

.. image:: ../images/NVFCL-diagrams-General-Scheme.drawio.svg
  :width: 400
  :alt: General Scheme
  :align: center

An example of deployment by the NFVCL can be an interconnected mix between VMs and PODs in Kubernetes as follow

.. image:: ../images/NVFCL-diagrams-NFVCL-example-NS.drawio.svg
  :width: 400
  :alt: Example deployment 1
  :align: center

Or maybe a Blueprint that creates only inter-connected Virtual Machines

.. image:: ../images/NVFCL-diagrams-NFVCL-example-NS2.drawio.svg
  :width: 400
  :alt: Example deployment 2
  :align: center


Getting started
***************

In order to be able to deploy Blueprints you will need to:

#. Create the Topology information (You can find a general description here :doc:`topology/topology`, :doc:`topology/topology_creation`)

    A. Including at least 1 VIM where VMs are deployed

    B. Including at least 1 K8S clusters where Helm Charts are deployed (The cluster can be generated using the dedicated K8S blueprint that does not require a K8S Cluster to be present in the Topology)

#. Set up the VIM :doc:`topology/topology_vim`

#. Deploy the desired Blueprint from the available list :doc:`blueprints/blueprint`. You can use the dedicated Blueprint to create
   and onboard a K8S cluster (over VMs) in the Topology.

Creation of Virtual Machines
****************************

.. image:: ../images/NVFCL-diagrams-VM-Creation.drawio.svg
  :width: 400
  :alt: VM Creation
  :align: center

Configuration of Virtual Machines
*********************************

.. image:: ../images/NVFCL-diagrams-VM-Configuration.drawio.svg
  :width: 400
  :alt: VM Configuration
  :align: center

Prometheus scraping
*******************
Prometheus is used as metrics database. Once a Prometheus server as been added to the Topology, it can be used by the NFVCL:

    - The NFVCL install exporters on supported Blueprints.

    - Edit the Prometheus configuration to scrape from all the installed exporters

For more details you can go to :doc:`prometheus/prometheus`

-------------

.. toctree::
   :maxdepth: 4
   :hidden:

   self

.. toctree::
   :caption: Installation
   :maxdepth: 4
   :hidden:

   quick_start
   helm
   docker

.. toctree::
   :caption: Topology
   :maxdepth: 4
   :hidden:

   topology/topology
   topology/topology_creation
   topology/topology_mgt
   topology/topology_nfvcl_k8s_onboarding.md
   topology/topology_vim

.. toctree::
   :caption: Blueprints
   :maxdepth: 4
   :hidden:

   blueprints/blueprint
   blueprints/k8s/k8s_blue_index
   blueprints/ueransim/ueransim_blue_index
   blueprints/5gcores/5gcore_blue_index

.. toctree::
   :caption: K8s Management
   :maxdepth: 4
   :hidden:

   kubernetes/k8s_man_index

.. toctree::
   :caption: Providers REST Server
   :maxdepth: 4
   :hidden:

   provider_rest_server/provider_rest_server

.. toctree::
   :caption: Data Analytics
   :maxdepth: 4
   :hidden:

   prometheus/prometheus
   prometheus/prometheus_server_conf
   prometheus/prometheus_top_add

.. toctree::
   :caption: More
   :maxdepth: 4
   :hidden:

   contacts
   credits

