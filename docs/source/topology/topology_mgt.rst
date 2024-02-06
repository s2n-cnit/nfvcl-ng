===================
Topology management
===================

We can edit the topology using dedicated API calls. We can add/remove/edit:

    - VIMs
    - Networks
    - Routers
    - PDUs
    - K8s Clusters
    - Prometheus servers

Create new resource
*******************
You can create a new resource (which are listed above) using the correspondent POST request that you can find in the SWAGGER (see home page).
We will use as example the POST to create a new VIM in the topology ``/v1/topology/vim``

.. code-block:: json

    {
        "name": "os_lab",
        "vim_type": "openstack",
        "schema_version": "1.0",
        "vim_url": "http://os-lab.maas:5000/v3",
        "vim_tenant_name": "paolo",
        "vim_user": "paolo",
        "vim_password": "pap3rin0",
        "config": {
            "insecure": true,
            "APIversion": "v3.3",
            "use_floating_ip": true
        },
        "networks": [
            "dmz-internal",
            "data_paolo"
        ],
        "routers": [],
        "areas": [
            3,
            4,
            5
        ]
    }


Update resource
***************


Delete resource
***************
