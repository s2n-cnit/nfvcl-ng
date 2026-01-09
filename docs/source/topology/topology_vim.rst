====================
Topology VIM setup
====================

After the Topology creation (step described in :doc:`topology_creation`), VIMs must be added in order for NFVCL to be able to deploy VMs.

There are three types of VIMs currently supported by NFVCL:

.. list-table:: Supported VIM Types
   :header-rows: 1
   :widths: 20 20 20

   * - Name (Doc Link)
     - ``vim_type`` value
     - Description
   * - OpenStack (`OpenStack VIM`_)
     - ``openstack``
     - https://www.openstack.org/
   * - Proxmox (`Proxmox VIM`_)
     - ``proxmox``
     - https://proxmox.com/
   * - External REST (`External REST VIM`_)
     - ``external_rest``
     - :doc:`../provider_rest_server/provider_rest_server`

Every Blueprint that require VMs should be deployable on any VIM type if configured correctly.
There are some limitation and known problems described in the dedicated VIM type documentation chapter.

Adding a VIM to the Topology
****************************

To create a new VIM in the Topology, you can use the ``POST /v1/topology/vim`` API endpoint.

.. warning::
    The topology must be created before adding any VIM.

There are some fields that are common to all VIM types, described here:
    - ``name``: Name of your vim
    - ``vim_url``: API URL
    - ``vim_user``: Username to access VIM
    - ``vim_password``: Password to access VIM
    - ``vim_type``: Any between the supported VIM types (see table above)
    - ``vim_timeout``: Operations timeout, in second, if not provided default is 180
    - ``ssh_keys``: A list of SSH public keys that will be injected in the VMs created on this VIM
    - ``networks``: List with the names of the networks registered in the topology that are connected to this VIM.
    - ``areas``: List of area id covered by this VIM, should not overlap with other VIMs, can be any integer value >= 1

OpenStack VIM
*************
Example request body for OpenStack VIM creation:

.. code-block:: json

    {
      "name": "oslab",
      "vim_type": "openstack",
      "vim_url": "http://os-lab.maas:5000/v3",
      "vim_user": "user01",
      "vim_password": "password01",
      "vim_timeout": null,
      "ssh_keys": [
      ],
      "vim_openstack_parameters": {
        "region_name": "RegionOne",
        "project_name": "user01-project",
        "user_domain_name": "Default",
        "project_domain_name": "Default"
      },
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
        1,
        2,
      ]
    }

For Openstack there is field ``vim_openstack_parameters`` :
    - ``region_name``
    - ``project_name``: OpenStack project, visible from web-ui
    - ``user_domain_name``
    - ``project_domain_name``

The fields ``region_name``, ``user_domain_name``, ``project_domain_name`` must be set according to your Openstack configuration, if your Openstack use default values then you can avoid to set them and use default values set by NFVCL.

.. warning::
    If NFVCL is running outside of the OpenStack network you neet to ensure that NFVCL is able to reach the VMs that it creates.
    If the VMs need a floating IP to be reachable, you need to set the ``use_floating_ip`` field in the ``config`` section to ``true``.

Proxmox VIM
***********
Example request body for Proxmox VIM creation:

.. code-block:: json

    {
      "name": "proxmoxtest",
      "vim_type": "proxmox",
      "vim_url": "192.168.17.100",
      "vim_user": "user01",
      "vim_password": "password01",
      "vim_timeout": null,
      "ssh_keys": [],
      "vim_proxmox_parameters": {
        "proxmox_realm": "pam",
        "proxmox_node": null,
        "proxmox_images_volume": "local",
        "proxmox_vm_volume": "local-lvm",
        "proxmox_token_name": "",
        "proxmox_token_value": "",
        "proxmox_otp_code": "",
        "proxmox_privilege_escalation": "sudo_without_password"
      },
      "config": {
        "insecure": true,
        "APIversion": "v3.3",
        "use_floating_ip": false
      },
      "networks": [],
      "routers": [],
      "areas": [
        100
      ]
    }

.. warning::
    The ``vim_url`` is currently the Proxmox IP and it is assumed that the API server is running on the default port.
    This is needed to also establish an SSH connection to the Proxmox host (see limitations below).

For Proxmox there is field ``vim_proxmox_parameters`` :
    - ``proxmox_realm``: Authentication realm, only ``pam`` is supported since we also need SSH access
    - ``proxmox_node``: Name of the node, visible from web-ui, can be left to null to auto-select the first node
    - ``proxmox_images_volume``: Name of the storage where VM images are stored
    - ``proxmox_vm_volume``: Name of the storage where VM disks will be created
    - ``proxmox_token_name``:
    - ``proxmox_token_value``:
    - ``proxmox_otp_code``:
    - ``proxmox_privilege_escalation``: Method used to escalate privilege for commands requiring root access, can be one of:
        - ``none``: The user is already root
        ..
            - ``sudo_with_password``: Use sudo and provide password
        - ``sudo_without_password``: Use sudo without password (requires proper sudoers configuration)
    - ``proxmox_resource_pool``: Name of the resource pool where you want to deploy the resources
Limitations
###########
Proxmox VE < 9.0.17

- Proxmox VIM require that NFVCL has SSH access to the Proxmox host, this is needed to perform some operations that are not available through the Proxmox API.
  Therefore the ``vim_user`` must be a valid user for SSH access.
- The SSH user must be root or a user with sudo privileges without password.
- Only the ``pam`` authentication realm is supported since we need SSH access.

This limitations is due to the lack of qcow2 and cloud-init custom script upload from the Proxmox API, see the following issues:
    - https://bugzilla.proxmox.com/show_bug.cgi?id=2424
    - https://bugzilla.proxmox.com/show_bug.cgi?id=2208

Features
###########

In Proxmox VE >= 9.0.17, the qcow2 and file upload has been added. NFVCL does not need anymore SSH access to the Proxmox host, this also allow the ``pve`` authentication realm.
It's now possible to use a non-administrator user. However, certain permissions must be assigned for NFVCL to work.
NFVCL automatically determines which version of Proxmox it's connecting to. This way, it knows whether it can use the new features or not.

PVE auth
###########
The roles with associated privileges required by NFVCL:
    - ``NFVCL_Datastore``: Datastore.AllocateSpace, Datastore.Allocate, Datastore.AllocateTemplate, Datastore.Audit
    - ``NFVCL_Sdn``: SDN.Audit, SDN.Use, SDN.Allocate
    - ``NFVCL_Sys``: Sys.AccessNetwork
    - ``NFVCL_Sys2``: Sys.Modify, Sys.Audit
    - ``NFVCL_Group``: Group.Allocate OPTIONAL


The path with associated role required by NFVCL:
    - ``/storage/YOUR_STORAGE`` -> ``NFVCL_Datastore``
    - ``/sdn`` -> ``NFVCL_Sdn``
    - ``/pool/YOUR_POOL`` -> ``Administrator``
    - ``/nodes/YOUR_NODES`` -> ``NFVCL_Sys``
    - ``/`` -> ``NFVCL_Sys2``
    - ``/access/group`` -> ``NFVCL_Group`` OPTIONAL

Permissions can be associated with a user.
Alternatively, they can be assigned to a group and added to it all users.
If you choose the second option, you must define the role and permissions marked as optional above.

External REST VIM
*****************
This VIM type allows to connect to an external REST API server that will act as a VIM or as a proxy.

There is a built-in REST server in NFVCL that can be used as remote VIM, see :doc:`../provider_rest_server/provider_rest_server` for more information.

Example request body for External REST VIM creation:

.. code-block:: json

    {
      "name": "extrestvim",
      "vim_type": "external_rest",
      "vim_url": "http://192.168.254.242:5003/v1",
      "vim_user": "",
      "vim_password": "",
      "vim_timeout": null,
      "ssh_keys": [],
      "vim_rest_parameters": {
        "remote_vim_name": "oslab",
        "local_agent_uuid": "eca604d4-626a-408e-bc54-a9ef11d421a0"
      },
      "config": {
        "insecure": false,
        "APIversion": "",
        "use_floating_ip": false
      },
      "networks": [],
      "routers": [],
      "areas": [
        1001
      ]
    }

If the remote REST VIM requires authentication you can provide it in the ``vim_user`` and ``vim_password`` fields.

For Proxmox there is field ``vim_rest_parameters`` :
    - ``remote_vim_name``: Name of the remote VIM registered on the REST server
    - ``local_agent_uuid``: Name of the node, visible from web-ui, can be left to null to auto-select the first node

.. warning::
    The ``local_agent_uuid`` is used to prevent a NFVCL instance from interacting with resources of another instance, this UUID MUST be different for each instance using the same remote REST server.

VM base images
**************
To create VMs on a VIM, NFVCL will automatically download the required image from a given URL (That can be found in the blueprint source code).
For most of the default blueprints, images will be downloaded from https://images.tnt-lab.unige.it/ so ensure that this URL is reachable from the VIM.

.. image:: ../../images/NVFCL-diagrams-NFVCL_VIM_interaction.drawio.svg
  :width: 400
  :alt: Alternative text
