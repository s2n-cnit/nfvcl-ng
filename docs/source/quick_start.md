# Quick Start

<!-- TOC -->
* [Quick Start](#quick-start)
  * [Start NFVCL](#start-nfvcl)
  * [Initialize the Topology](#initialize-the-topology)
  * [Add more VIMs (optional)](#add-more-vims-optional)
  * [Create a K8S cluster to be added to the topology](#create-a-k8s-cluster-to-be-added-to-the-topology)
  * [Deploy a Blueprint](#deploy-a-blueprint)
<!-- TOC -->

> **Note:** Before starting NFVCL, ensure you have a proper configuration file set up.
> The default configuration file is located at `config/config.yaml`.
> For Docker deployments, see the [Docker guide](docker.md) and use `config/config_compose.yaml` as a reference.

> **Note:** All the following requests must be sent in JSON format to the NFVCL API.


## Start NFVCL
For docker deployments, please refer to the [Docker guide](docker.md).
For local deployments, please refer to the [Local guide](local.md).

## Initialize the Topology
Initialize the topology by sending a POST request to `/v1/topology` with the following body:

**This request will create a topology with a single OpenStack VIM.**

> **Warning:** At least one VIM must be present in the topology (or added afterward). Openstack and Proxmox VIMs are supported.

```json
{
  "id": "topology",
  "callback": null,
  "vims": [
    {
      "name": "openstack_test",
      "vim_type": "openstack",
      "vim_url": "http://10.1.1.1:5000/v3",
      "vim_user": "nfvcl",
      "vim_password": "vim_user_password",
      "ssh_keys": [
        "ssh-rsa your-pub-key your-pub-key-name"
      ],
      "vim_openstack_parameters": {
        "project_name": "nfvcl_test"
      },
      "config": {
        "insecure": true,
        "APIversion": "v3.3",
        "use_floating_ip": false
      },
      "networks": [],
      "areas": [
        1
      ]
    }
  ],
  "kubernetes": [],
  "networks": [],
  "routers": [],
  "pdus": [],
  "prometheus_srv": []
}
```

## Add more VIMs (optional)
**Note:** Adding more VIMs is optional and can be done by sending additional POST requests to `/v1/topology/vim`

```json
{
      "name": "os_123",
      "vim_type": "openstack",
      "vim_url": "http://os-123.local:5000/v3",
      "vim_user": "admin",
      "vim_password": "passwd",
      "vim_timeout": null,
      "ssh_keys": [
        "ssh-rsa your-pub-key your-pub-key-name"
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
        "control",
        "data"
      ],
      "routers": [],
      "areas": [
        4
      ]
}
```

For Proxmox VIMs:
```json
{
  "name": "proxmoxtest",
  "vim_type": "proxmox",
  "vim_url": "192.168.17.68",
  "vim_user": "root",
  "vim_password": "password",
  "vim_timeout": null,
  "ssh_keys": [
    "ssh-rsa your-pub-key your-pub-key-name"
  ],
  "vim_proxmox_parameters": {
    "proxmox_realm": "pam",
    "proxmox_node": null,
    "proxmox_images_volume": "local",
    "proxmox_vm_volume": "local-lvm",
    "proxmox_token_name": "",
    "proxmox_token_value": "",
    "proxmox_otp_code": "",
    "proxmox_privilege_escalation": "none",
    "proxmox_resource_pool": null
  },
  "vim_rest_parameters": null,
  "networks": [],
  "routers": [],
  "areas": [
    100
  ]
}
```

## Create a K8S cluster to be added to the topology
Using the dedicated Blueprint, it is possible to create a K8S cluster and add it to the Topology.

**Note:** If there is no K8S cluster in the topology, most Blueprints will fail. They use K8S to deploy services or parts of services.

Post request to `/nfvcl/v2/api/blue/k8s` with the following body:

```json
{
  "cni": "flannel",
  "topology_onboard": true,
  "password": "testPWD",
  "ubuntu_version": "UBUNTU24",
  "install_plugins": true,
  "require_port_security_disabled": true,
  "master_flavors": {
    "memory_mb": "4096",
    "storage_gb": "32",
    "vcpu_count": "4"
  },
  "areas": [
    {
      "area_id": 4,
      "is_master_area": true,
      "mgmt_net": "control",
      "additional_networks": ["data_network"],
      "load_balancer_pools_ips": [
        "10.1.1.100",
        "10.1.1.101",
        "10.1.1.102"
      ],
      "worker_replicas": 1,
      "worker_flavors": {
        "memory_mb": "4096",
        "storage_gb": "32",
        "vcpu_count": "6"
      }
    }
  ]
}
```

**Response:**

```json
{
  "status": "deploying",
  "detail": "Blueprint COEU04 is being deployed...",
  "result": {},
  "task_id": "3a8f204e-0837-43a5-a048-71816fa517de"
}
```

After the creation has been finished, the K8S cluster will be added to the topology. You can check the status of the Blueprint creation by sending a GET request to `/nfvcl/v2/api/blue`
or by obtaining the status of the task (task ID is in the creation response) from the NFVCL API GET `/v2/utils/get_task_status?task_id=::TASK_ID::`.

You can check the presence of the K8S cluster in the topology by sending a GET request to `/v1/topology`.

``` json
{
  "id": "topology",
  "callback": null,
  "vims": [
    {
      "name": "os_test_local",
      "vim_type": "openstack",
      "vim_url": "http://os-test.local:5000/v3",
      "vim_user": "admin",
      
      ...
      
      
      "areas": [
        4
      ]
    }
  ],
  "kubernetes": [
    {
      "name": "COEU04",
      "provided_by": "NFVCL",
      "blueprint_ref": "COEU04",
      "deployed_blueprints": [],
      "credentials": ...
      "vim_name": "os_test_local",
      "k8s_version": "v1.30",
      "networks": [
        {
          "name": "control",
          "interface_name": null,
          "multus_enabled": false,
          "ip_pools": []
        },
        {
          "name": "data_network",
          "interface_name": null,
          "multus_enabled": false,
          "ip_pools": []
        }
      ],
      "areas": [
        4
      ],
      "cni": "",
      "cadvisor_node_port": 30080,
      "nfvo_status": "not_onboarded",
      "nfvo_onboard": false,
      "anti_spoofing_enabled": false,
      "k8s_monitoring_metrics": null
    }
  ],
  "networks": [],
  "routers": [],
  "pdus": [],
  "prometheus_srv": [],
  "grafana_srv": [],
  "loki_srv": []
}
```

## Deploy a Blueprint
You can choose from the list of available Blueprints the one you want to deploy. Refer to the Blueprints documentation for more details.

