Home
====

.. note::

   This project is under active development.

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

In order to be able to deploy Blueprints you will need to

#. Create the Topology information (You can find a general description here :doc:`topology/topology`, :doc:`topology/topology_creation`)

    A. Including at least 1 VIM where VMs are deployed

    B. Including at least 1 K8S clusters where Helm Charts are deployed (The cluster can be generated and added later using the dedicated K8S blueprint)

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
   :maxdepth: 2
   :hidden:

   self

.. toctree::
   :caption: Topology
   :maxdepth: 2
   :hidden:

   topology/topology
   topology/topology_creation
   topology/topology_mgt
   topology/topology_nfvcl_k8s_onboarding.md
   topology/topology_vim

.. toctree::
   :caption: Blueprints
   :maxdepth: 2
   :hidden:

   blueprints/blueprint
   blueprints/free5gc/free5gc_blue_index
   blueprints/k8s/k8s_blue_index
   blueprints/ueransim/ueransim_blue_index
   blueprints/vyos/vyos_blue_index
   blueprints/openairinterface/openairinterface_blue_index

.. toctree::
   :caption: K8s Management
   :maxdepth: 2
   :hidden:

   kubernetes/k8s_man_index

.. toctree::
   :caption: Data Analytics
   :maxdepth: 2
   :hidden:

   prometheus/prometheus

.. toctree::
   :caption: More
   :maxdepth: 2
   :hidden:

   contacts

