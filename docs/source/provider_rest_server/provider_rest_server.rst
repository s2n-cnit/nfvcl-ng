====================
Provider REST Server
====================

.. contents::
   :local:

The NFVCL Provider REST Server is a microservice that exposes a REST API to interact with different VIMs.
It acts as an intermediary between the NFVCL core and the underlying VIMs, allowing better control over the VIM's credentials and configurations.

The Provider REST Server supports all the VIM types that can normally be used in NFVCL, such as OpenStack, Proxmox, and External REST VIMs (Recursive REST not tested).

Configuration
*************
The Provider REST Server can be configured using environment variables or a configuration file like NFVCL.

Example configuration file (``config/providers_rest/config.yaml``):

.. code-block:: yaml

    log_level: "20" # 20 is info, 10 is debug, 5 is trace
    nfvcl_providers:
      port: "5003"
      ip: "0.0.0.0"
      workers: 10
      admin_uuid: "admin" # CHANGE THIS!
    mongodb:
      host: "127.0.0.1"
      port: "27017"
      db: "nfvcl-providers-rest"

Most of the configuration parameters are similar to those used in NFVCL.

.. warning::
    The ``admin_uuid`` parameter must be changed to a unique value for each Provider REST Server instance.
    This UUID need to be used to perform API operations with admin privileges.

Running
*******
To run the Provider REST Server using docker compose, use the following command:

.. code-block:: bash

    docker compose -f docker-compose/providers_rest/compose-dev.yaml up -d


