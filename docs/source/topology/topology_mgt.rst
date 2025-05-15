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
We will see two example, Openstack first and then Proxmox, of POST to create VIM in the topology ``/v1/topology/vim``

.. code-block:: json

 {
      "name": "string",
      "vim_type": "openstack",
      "vim_url": "string",
      "vim_user": "admin",
      "vim_password": "admin",
      "vim_timeout": TIMEOUT_IN_SECOND,
      "ssh_keys": [
        "string"
      ],
      "vim_openstack_parameters": {
        "region_name": "RegionOne",
        "project_name": "admin",
        "user_domain_name": "Default",
        "project_domain_name": "Default"
      },
      "config": {
        "insecure": true,
        "APIversion": "v3.3",
        "use_floating_ip": false
      },
      "networks": [
        "string"
      ],
      "routers": [
        "string"
      ],
      "areas": [
        0
      ]
 }


.. code-block:: json

  {
      "name": "string",
      "vim_type": "proxmox",
      "vim_url": "string",
      "vim_user": "admin",
      "vim_password": "admin",
      "vim_timeout": TIMEOUT_IN_SECOND,
      "ssh_keys": [
        "string"
      ],
      "vim_proxmox_parameters": {
        "proxmox_realm": "pam",
        "proxmox_node": "null",
        "proxmox_images_volume": "local",
        "proxmox_vm_volume": "local-lvm",
        "proxmox_token_name": "YOUR_TOKEN_NAME",
        "proxmox_token_value": "YOUR_TOKEN_VALUE",
        "proxmox_otp_code": ""
      },
      "config": {
        "insecure": true,
        "APIversion": "v3.3",
        "use_floating_ip": false
      },
      "networks": [
        "string"
      ],
      "routers": [
        "string"
      ],
      "areas": [
        0
      ]
  }

.. warning::
    For Proxmox the field *proxmox_token_name* is the name of the token that you can find in your proxmox server
    Datacenter > Permission > Api Tokens and in the table **Token Name**.
    Token and Otp code are optional paramaters, instead *vim_user* and *vim_password* must be provided.

Delete resource
***************
To delete a resource it is sufficient to make a `DELETE` request giving the resource ID.
We will use as example the DELETE to delete a VIM ``/v1/topology/vim/{{ VIM_ID }}``
