Prometheus
==========

The NFVCL offers the possibility to add to the topology a Prometheus server instance.
The Prometheus server is **EXTERNAL** to the NFVCL and must be running and a dynamic configuration file must be configured to be
read by Prometheus (see :doc:`prometheus_server_conf`). This file will be used to add or remove scraping jobs.

When required by a Blueprint, the NFVCL is able to add a scraping job (through updating a configuration file) on a Prometheus server such that it collects data
from one or more exporters configured on the Blueprint VNFs. The operation **must to be implemented** in the Blueprint code.

Once the Prometheus instance has been added to the topology (:doc:`prometheus_top_add`), it is possible to configure
it such that it scrapes data from elements composing the Blueprint.
Example
*******
An implementation example is offered by K8S blueprint. With the dedicated API call ``{{ base_url }}/nfvcl/v2/api/blue/k8s/enable_prom/string``

.. warning::
    The prom_server_id must correspond to an existing prometheus server ID in the topology!

The K8S Blueprint uses VM images with Prometheus Node Exported already installed and running.

--------------------------------------------------

.. toctree::
    prometheus_top_add
    prometheus_server_conf
