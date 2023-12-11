=================
Topology creation
=================

The first step, before creating blueprints with NFVCL, is the creation of the topology.
NFVCL needs VIMs (OpenStack instances) to run most of its blueprint. You will see that in the topology creation request
there is a list of VIMs, you should add there at least valid one.

.. warning::
    The VIM user must be administrator for the target project

With the next step the OpenStack server will be registered in OSM and NFVCL. The networks of the VIM must be appended to the
network list. At least a management network should be present.
``POST /v1/topology/``

Example request body:

.. code-block:: json

    {
      "id": "topology",
      "callback": null,
      "vims": [
        {
          "name": "OS-LAB",
          "vim_type": "openstack",
          "schema_version": "1.0",
          "vim_url": "http://os-lab.maas:5000/v3",
          "vim_tenant_name": "exampleuser",
          "vim_user": "exampleuser",
          "vim_password": "examplepassword",
          "config": {
            "insecure": true,
            "APIversion": "v3.3",
            "use_floating_ip": false
          },
          "networks": [
            "dmz-internal",
            "data-net"
          ],
          "routers": [],
          "areas": [
            0,
            1
          ]
        }
      ],
      "kubernetes": [],
      "networks": [
        {
          "name": "dmz-internal",
          "external": false,
          "type": "vxlan",
          "vid": null,
          "dhcp": true,
          "ids": [],
          "cidr": "10.255.255.0/24",
          "gateway_ip": "10.255.255.254",
          "allocation_pool": [],
          "reserved_ranges": [],
          "dns_nameservers": []
        },
        {
          "name": "data-net",
          "external": false,
          "type": "vxlan",
          "vid": null,
          "dhcp": true,
          "ids": [],
          "cidr": "10.255.251.0/24",
          "gateway_ip": null,
          "allocation_pool": [],
          "reserved_ranges": [],
          "dns_nameservers": []
        }
      ],
      "routers": [],
      "pdus": [],
      "prometheus_srv": []
    }

The ``name`` field is the name of the topology.

In the ``vims`` list in the object representing the OpenStack server this fields need to be changed to fit your configuration:

    - ``vim_url``: OpenStack API URL
    - ``vim_tenant_name``: OpenStack Project name
    - ``vim_user``: OpenStack user
    - ``vim_password``: OpenStack user password
    - ``networks``: List with the names of the OpenStack networks that will be used by blueprints, at least one network is required.
    - ``areas``: List of area id covered by this topology

The ``networks`` list contain the details of the networks listed in ``vims[0].networks``.
