# Kubernetes Blueprint
The Kubernetes Blueprint is dedicated to the lifecycle management of a K8S cluster (creation, deletion,
add node, install K8S plugins).

It acts on the required VIMs to create a variable number of Virtual Machines on witch K8S software is configured.
One of these VMs acts as the cluster controller while the others act as workers. Based on the request some nodes of the 
cluster can be deployed in an area or in another (multi vim deployment)

The request of the creations contains important details like the network to be used as management network (See [Deployment](#deployment)).

The Blueprint dedicated APIs base url is `{{ base_url }}/nfvcl/v2/api/blue/k8s`

## Deployment
Here you can see a simple request (with no optional data) that is deploying a K8S cluster in the `area=3` (the VIM should be present in the Topology).
One and only one Core area must always be present! You can choose where the master node should be deployed. 
Using the worker_replicas parameter, you can choose how many workers will be deployed in that area.

A lot of the following parameters can be omitted because they have a default values, you can see what is optional in the
swagger (http://{{NFVCL_IP}}:5002/docs)

```
POST on {{ base_url }}/nfvcl/v2/api/blue/k8s
```

```json
{
  "cni": "flannel",
  "pod_network_cidr": "10.254.0.0/16",
  "service_cidr": "10.200.0.0/16",
  "topology_onboard": true,
  "password": "ubuntu",
  "install_plugins": true,
  "require_port_security_disabled": true,
  "master_flavors": {
    "memory_mb": "4096",
    "storage_gb": "32",
    "vcpu_count": "8"
  },
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "additional_networks": [
        "data_paolo"
      ],
      "load_balancer_pools_ips": [],
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

For each area we have a different configuration, the area ID identifies the VIM to be used in the Topology.

The other parameters description can be found in the Swagger. Some attention can be devoted to:
- `mgmt_net` that is the network used by NFVCL to connect to created VMs and used for connection between nodes.
- `additional_networks` connected to every VM in THAT area can be useful to the load balancer
- `load_balancer_pools_ips` ips to be used by the load balancer to expose services. These IPs must be configured 
at virtualization/physical layer such that they are reachable till the VM. Then MetalLB will announce these IPs in the
relative area.

### Plugin installation
To install a plugin in a deployed k8s blueprint you can use APIs of the K8S management part (not part of the blueprint):
POST API on
```
http://192.168.254.11:5002/k8s/{CLUSTER_ID}/plugins
```

with the following content:
```json
{
  "plugin_list": [
    "flannel",
    "metallb",
    "openebs"
  ],
  "load_balancer_pool": {
    "pool_name": "test",
    "ip_list": ["192.168.254.10","192.168.254.13","192.168.254.16"],
    "host_names": ["uhhsa4-vm-k8s-c", "uhhsa4-vm-w-0"]
  },
  "skip_plug_checks": false
}
```

## Adding Nodes to the cluster
> This call is working only on K8S deployed using the Blueprint system, NOT on external clusters.
> {.is-warning}

It is possible to add nodes to an existing and previously created K8S Blueprint. To do this it is sufficient to call the 
POST API on
```
{{ base_url }}/nfvcl/v2/api/blue/k8s/add_node
```

with the following content:
```json
{
  "areas": [
    {
      "area_id": 1,
      "is_master_area": false,
      "mgmt_net": "dmz-internal",
      "additional_networks": ["data_paolo"],
      "worker_replicas": 1,
      "worker_flavors": {
        "memory_mb": "8192",
        "storage_gb": "32",
        "vcpu_count": "6"
      }
    }
  ]
}
```
Note that master area has been set to FALSE cause the master has been already deployed.

## Removing Nodes from the cluster
DELETE on
```
http://NFVCL_IP:NFVCL_PORT/nfvcl/v2/api/blue/k8s/del_workers?blue_id=UHHSA4
```

```json
{
  "node_names": [
    "uhhsa4_vm_w_0"
  ]
}
```
