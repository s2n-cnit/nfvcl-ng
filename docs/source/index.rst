Welcome to NFVCL-ng's documentation!
====================================
.. note::

   This project is under active development. **We are developing and testing implementations for Open Air Interface(OAI) and SD-Core.**


The installation procedure is described in the main `README <https://github.com/s2n-cnit/nfvcl-ng>`_.

The NFVCL is working through REST API calls, you can see every available API in the offered swagger by the NFVCL.
You can find the swagger at URL: http://NFVCL-IP:5002/docs

VIM onboarding
**************

Once the NFVCL is installed and running, the first operation that must be performed
is the creation of :doc:`topology/topology_creation`.

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
     - K8s
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

Once the topology has been created, and, at least one VIM account is configured, it is possible to instantiate new Blueprints like K8S and VyOS.
Free5GC will need a working and onboarded K8S cluster.
Every blueprint needs different calls with different bodies to be deployed.
You can see the creation schema for each Blueprint in the NFVCL swagger.
Once a blueprint has been deployed it can offer different day 2 and day N functionalities.

The current version of NFVCL can deploy the following blueprints:

.. list-table:: Blueprint list
   :widths: 25 50 50 25
   :header-rows: 1

   * - Blueprint name
     - Type
     - Requirements
     - Notes
   * - :doc:`blueprints/k8s/k8s_blue_index`
     - Kubernetes cluster
     - VIM to deploy VMs
     -
   * - :doc:`blueprints/free5gc/free5gc_blue_index`
     - 5G Core
     - K8s cluster onboarded in OSM
     -
   * - OpenAirInterface
     - 5G Core
     - K8s cluster onboarded in OSM + VIM
     -
   * - SDCore
     - 5G Core
     - K8s cluster onboarded in OSM + VIM
     -
   * - :doc:`blueprints/vyos/vyos_blue_index`
     - Virtual Router
     - VIM
     -
   * - :doc:`blueprints/ueransim/ueransim_blue_index`
     - gNodeB and UE emulator
     - VIM
     -

Prometheus scraping
*******************
:doc:`prometheus/prometheus`

-------------

Documentation contents
**********************

.. toctree::
   :caption: Topology
   :maxdepth: 2
   :hidden:

   topology/topology_creation

.. toctree::
   :caption: Blueprints
   :maxdepth: 2
   :hidden:

   blueprints/free5gc/free5gc_blue_index
   blueprints/k8s/k8s_blue_index
   blueprints/ueransim/ueransim_blue_index
   blueprints/vyos/vyos_blue_index

.. toctree::
   :caption: Data Analitics
   :maxdepth: 2
   :hidden:

   prometheus/prometheus

