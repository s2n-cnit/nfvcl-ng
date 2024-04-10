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

The structure of the data to be used in requests can be found in the bottom of NFVCL Swagger ( http://NFVCL-IP:5002/docs )

Create new resource
*******************
You can create a new resource (which are listed above) using the correspondent `POST` request that you can find in the Swagger ( http://NFVCL-IP:5002/docs ).
We will use as example the POST to create a new VIM in the topology ``/v1/topology/vim``

.. code-block:: json

    {
        "name": "os_lab",
        "vim_type": "openstack",
        "schema_version": "1.0",
        "vim_url": "http://os-lab.maas:5000/v3",
        "vim_tenant_name": "paolo",
        "vim_user": "paolo",
        "vim_password": "password",
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
You can update a new resource (which are listed above) using the correspondent `PUT` request that you can find in the SWAGGER (see home page).
We will use as example the POST to update a VIM in the topology ``/v1/topology/vim``

.. code-block:: json

    {
      "name": "os_ntua",
      "networks_to_add": ["nephele-vpn-network"],
      "networks_to_del": ["public1"],
      "routers_to_add": [],
      "routers_to_del": [],
      "areas_to_add": [],
      "areas_to_del": []
    }

Delete resource
***************
To delete a resource it is sufficient to make a `DELETE` request giving the resource ID.
We will use as example the DELETE to delete a VIM ``/v1/topology/vim/{{ VIM_ID }}``
