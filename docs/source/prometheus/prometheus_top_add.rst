Add Prometheus server
=====================

In order to add a Prometheus server to the topology it is sufficient to use the specific API call:

``POST /v1/topology/prometheus``

Example request body:

.. code-block:: json

    {
        "id": "instance_id",
        "ip": "192.168.1.1",
        "port": "9090",
        "user": "ubuntu",
        "password": "sasd!sdsad-sdaa",
        "ssh_port": 22,
        "targets": [],
        "sd_file_location": "/home/ubuntu/sd_file_nfvcl.yaml"
    }

.. warning::
    The user must have permissions to edit the SD file!
