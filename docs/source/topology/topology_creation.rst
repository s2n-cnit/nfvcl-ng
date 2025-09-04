=================
Topology creation
=================

The first step, before creating blueprints with NFVCL, is the creation of the topology.
NFVCL needs VIMs (OpenStack or Proxmox instances) to run most of its blueprint. You will see that in the topology creation request
there is a list of VIMs, you should add there at least valid one.

.. warning::
    The VIM user must be administrator for the target project
.. warning::
    When adding a VIM, it is really important to use the correct value for the field use_floating_ip, otherwise, the NFVCL cannot talk to the VNF(VM or Pod) if the NFVCL instance is outside the openstack network.

With the next step the OpenStack server will be registered in NFVCL. The networks of the VIM must be appended to the network list. At least a management network should be present.
``POST /v1/topology/``

Example request body of a working Topology with Openstack and Proxmox vims:

.. code-block:: json

     {
       "id":"topology",
       "callback":null,
       "vims":[
          {
             "name":"example_name",
             "vim_type":"openstack",
             "vim_url":"URL_OPENSTACK",
             "vim_user":"example_user",
             "vim_password":"example_pwd",
             "vim_timeout":null,
             "ssh_keys":[

             ],
             "vim_openstack_parameters":{
                "region_name":"RegionOne",
                "project_name":"PROJECT_NAME",
                "user_domain_name":"Default",
                "project_domain_name":"Default"
             },
             "config":{
                "insecure":true,
                "APIversion":"v3.3",
                "use_floating_ip":false
             },
             "networks":[
                "OPENSTACK_NET_NAME"
             ],
             "routers":[],
             "areas":[
                1
             ]
          },
          {
             "name":"example_name",
             "vim_type":"proxmox",
             "vim_url":"URL_PROXMOX",
             "vim_user":"example_user",
             "vim_password":"example_pwd",
             "vim_timeout":null,
             "ssh_keys":[

             ],
             "vim_proxmox_parameters":{
                "proxmox_realm":"pam",
                "proxmox_node":null,
                "proxmox_images_volume":"local",
                "proxmox_vm_volume":"local-lvm",
                "proxmox_token_name":"TOKEN_NAME",
                "proxmox_token_value":"TOKEN_VALUE",
                "proxmox_otp_code":""
             },
             "config":{
                "insecure":true,
                "APIversion":"v3.3",
                "use_floating_ip":false
             },
             "networks":[
                "PROXMOX_NET_NAME"
             ],
             "routers":[],
             "areas":[
                2
             ]
          }
       ],
       "kubernetes":[],
       "networks":[
          {
    		  "name": "PROXMOX_NET_NAME",
    		  "external": false,
    		  "type": "vxlan",
    		  "vid": null,
    		  "dhcp": true,
    		  "ids": [],
    		  "cidr": "CIDR_OF_THE_NETWORK",
    		  "gateway_ip": "GATEWAY_OF_THE_NETWORK",
    		  "allocation_pool": [],
    		  "reserved_ranges": [],
    		  "dns_nameservers": []
          },
          {
             "name":"OPENSTACK_NET_NAME",
             "external":false,
             "type":"vxlan",
             "vid":null,
             "dhcp":true,
             "ids":[],
             "cidr":"CIDR_OF_THE_NETWORK",
             "gateway_ip":"GATEWAY_OF_THE_NETWORK",
             "allocation_pool":[],
             "reserved_ranges":[],
             "dns_nameservers":[]
          }
       ],
       "routers":[],
       "pdus":[],
       "prometheus_srv":[]
     }

The Topology can also be initialized as empty and then it is possible to use the Management APIs to add required data
to deploy Blueprints. You can find out more information in the dedicated :doc:`topology_creation.rst` page.


The ``name`` field is the name of the topology.

In the ``vims`` list, the object representing the OpenStack/Proxmox server fields need to be changed to fit your configuration:

    - ``name``: Name of your vim
    - ``vim_url``: OpenStack/Proxmox API URL
    - ``vim_user``: OpenStack/Proxmox user
    - ``vim_password``: OpenStack/Proxmox user password
    - ``vim_type``: *openstack* or *proxmox* based on what you want to create
    - ``vim_timeout``: operation timeout, in second, if not provided default is 180
    - ``ssh_keys``: Set in cloudinit, but optional
    - ``networks``: List with the names of the OpenStack/Proxmox networks that will be used by blueprints, at least one network is required.
    - ``areas``: List of area id covered by this topology

For Openstack there is field *vim_openstack_parameters* :

    - ``region_name``
    - ``project_name``: OpenStack project, visible from web-ui
    - ``user_domain_name``
    - ``project_domain_name``

The fields **region_name**, **user_domain_name**, **project_domain_name** must be set according to your Openstack configuration, if your Openstack use default values then you can avoid to set them and use default values set by NFVCL.

For Proxmox there is field *vim_proxmox_parameters* :

    - ``proxmox_realm``
    - ``proxmox_node``: Name of the node, visible from web-ui
    - ``proxmox_images_volume``
    - ``proxmox_vm_volume``
    - ``proxmox_token_name``: These field is Optional
    - ``proxmox_token_value``: These field is Optional
    - ``proxmox_otp_code``: These field is Optional

The fields **proxmox_realm**, **proxmox_images_volume**, **proxmox_vm_volume** must be set according to your Proxmox configuration, if your Proxmox use default values then you can avoid to set them and use default values set by NFVCL.

The ``networks`` list contain the details of the networks listed in ``vims[0].networks``.
