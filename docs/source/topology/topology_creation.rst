=================
Topology creation
=================

The first step, before creating blueprints with NFVCL, is the creation of the topology.
NFVCL needs VIMs (OpenStack or Proxmox instances) to run most of its blueprints. You will see that in the topology creation request
there is a list of VIMs, you should add there at least valid one.

The topology can be created with a ``POST /v1/topology/`` request, an example of request body is shown here:

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
             "ssh_keys":[],
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
             "ssh_keys":[],
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
       "kubernetes":[

       ],
       "networks":[
          {
             "name":"PROXMOX_NET_NAME",
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

In this example the topology contains two VIMs, one OpenStack and one Proxmox, the topology can also be created empty and VIMs can be added later with the dedicated API (see :doc:`topology_vim`).
