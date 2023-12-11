Prometheus
==========

The NFVCL offers the possibility to add to the topology a Prometheus server instance.
The Prometheus server is **EXTERNAL** to the NFVCL and must be running and a dynamic configuration file must be configured to be
read by Prometheus (see :doc:`prometheus_server_conf`). This file will be used to add or remove scraping jobs.

When required by a blueprint, the NFVCL is able to add a scraping job (through updating a configuration file) on a Prometheus server such that it collects data
from one or more exporters configured on the blueprint VNFs.

Once the instance has been added to the topology (:doc:`prometheus_top_add`), it is possible to configure
it such that it scrapes data from a VNF internal to a blueprint. The functionality must be implemented by the specific blueprint.

Example
*******
An implementation example is offered by K8S blueprint. With the dedicated API call ``/nfvcl/v1/api/blue/K8sBeta/{blue_id}/en_prom``

Example request body:

.. code-block:: json

    {
      "callbackURL": "not_used_for_now",
      "operation": "monitor",
      "prom_server_id": "string"
    }

.. warning::
    The prom_server_id must correspond to an existing prometheus server ID in the topology!

In this case, in each node of the K8s cluster an exporter is installed. Then the list of all exporters is added to the SD file
in the specified Prometheus server (belonging to the topology) that starts to collect data from these servers.

--------------------------------------------------

.. toctree::
    prometheus_top_add
    prometheus_server_conf
