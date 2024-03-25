Welcome to NFVCL-ng's documentation!
====================================
.. note::

   This project is under active development.


The installation procedure is described in the main `README <https://github.com/s2n-cnit/nfvcl-ng>`_.

The NFVCL is working through REST API calls, you can see every available API in the swagger offered by the NFVCL.
You can find the swagger at URL: http://NFVCL-IP:5002/docs

Topology Creation and VIM onboarding
************************************

What is the topology? You can find a general description here :doc:`topology/topology`
Once the NFVCL is installed and running, the first operation that must be performed
is the creation of :doc:`topology/topology_creation`.

VIM setup
*********

The second step is to prepare VIMs: they should have images ready to be deployed. The images ready in a VIM should include
(name - description - used by blueprint)

.. list-table:: Images to be uploaded in every VIM
   :widths: 25 25 50
   :header-rows: 1

   * - Image name
     - Image
     - Used by blueprint
   * - ubuntu2204
     - Ubuntu 22.04 LTS
     - K8s (v1)
   * - k8s-base
     - Ubuntu 22.04 LTS + K8S installed
     - K8s (v2)
   * - ubuntu2004
     - Ubuntu 20.04 LTS
     - Deprecated blueprints
   * - ubuntu1804
     - Ubuntu 18.04 LTS
     - Deprecated blueprints
   * - vyos
     - VyOS (see build :doc:`blueprints/vyos/vyos_blue_creation`)
     - VyOS
   * - ...
     - ...
     - ...

For **Ubuntu** images you can use the API at (POST - /v1/openstack/update_images) to automatically **download/update**
Ubuntu images, it takes several minutes.

Blueprints
**********
To see the Blueprint general description you can go there :doc:`blueprints/blueprint`)

The current version of NFVCL can deploy the following Blueprints:

.. list-table:: Blueprint list
   :widths: 25 50 50 25
   :header-rows: 1

   * - Blueprint name
     - Type
     - Requirements
     - Blue Version
   * - :doc:`blueprints/k8s/k8s_blue_index`
     - Kubernetes cluster
     - VIM(s) for VMs deployment
     - 2
   * - :doc:`blueprints/free5gc/free5gc_blue_index`
     - 5G Core
     - K8s cluster onboarded in OSM
     - 1
   * - :doc:`blueprints/openairinterface/openairinterface_blue_index`
     - OpenAirInterface
     - 5G Core
     - K8s cluster onboarded in OSM + VIM
     - 1
   * - SDCore
     - 5G Core
     - K8s cluster onboarded in OSM + VIM
     - 1
   * - :doc:`blueprints/vyos/vyos_blue_index`
     - Virtual Router
     - VIM
     - 1
   * - :doc:`blueprints/ueransim/ueransim_blue_index`
     - gNodeB and UE emulator
     - VIM
     - 1

Prometheus scraping
*******************
Prometheus is used as metrics database. Once a Prometheus server as been added to the Topology, it can be used by the NFVCL:
- The NFVCL install exporters on supported Blueprints.
- Edit the Prometheus configuration to scrape from all the installed exporters

For more details you can go to :doc:`prometheus/prometheus`

-------------

Documentation contents
**********************

.. toctree::
   :caption: Topology
   :maxdepth: 2
   :hidden:

   topology/topology
   topology/topology_creation
   topology/topology_mgt
   topology/topology_nfvcl_k8s_onboarding.md

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

