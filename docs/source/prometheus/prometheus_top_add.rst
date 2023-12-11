Add Prometheus server
=====================

In order to add a Prometheus server to the topology it is sufficient to use the specific API call:

``POST /v1/topology/prometheus``

Example request body:

.. code-block:: json

    {
      "id": "prom_serv_id",
      "ip": "127.0.0.1",
      "port": "9100",   ##!!!TO REMOVE -> The port of Prometheus
      "user": "ubuntu",
      "password": "ubuntu",
      "ssh_port": 22,
      "jobs": [],   ##!!!TO REMOVE -> It will be configured by NFVCL
      "sd_file_location": "sd_targets.yml"
    }

.. warning::
    The user must have permissions to edit the SD file!
