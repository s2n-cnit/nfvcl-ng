# Kubernetes Blueprint deployment
The request of the creations contains important details like the network to be used as management network (See [Deployment](#deployment)).

## Deployment
Here you can see a simple request (with no optional data) that is deploying a K8S cluster in the `area=1` (the VIM should be present in the Topology).
**One and only one** core area must always be present! With this parameter you can choose where the master node should be deployed. 
Using the `worker_replicas` parameter, you can choose how many workers will be deployed in that area.

A lot of the following parameters can be omitted because they have a default values, you can see what is optional in the swagger (`http://{{NFVCL_IP}}:5002/docs`)

For each area we have a different configuration, the area ID identifies the VIM to be used in the Topology.

The parameters description can be found in the Swagger. Some attention can be devoted to:
- `mgmt_net` that is the network used by NFVCL to connect to created VMs and used for connection between nodes.
- `additional_networks` connected to every VM in THAT area can be useful to the load balancer
- `load_balancer_pools_ips` ips to be used by the load balancer to expose services. These IPs must be configured 
at virtualization/physical layer such that they are reachable till the VM. Then MetalLB will announce these IPs in the
relative area.

To start the creation of a blueprint instance you need to perform an API POST request on
```
{{ base_url }}/nfvcl/v2/api/blue/k8s
```
And the body should be composed like this (`dmz-internal` net should exist and `192.168.254.201` should be reserved for the load balancer):
```json
{
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "load_balancer_pools_ips": ["192.168.254.201"],
      "worker_replicas": 1
    }
  ]
}
```

The creation of a K8S cluster can have different parameters, but in the previous request they are not present, why?
A lot of them are `optional` with default values and can be used when required by the user. You can see the following example that is creating the
same cluster of the previous API call with few differences (the list of IP for the load balancer).

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
    "vcpu_count": "4"
  },
  "areas": [
    {
      "area_id": 3,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "load_balancer_pools_ips": ["192.168.254.201","192.168.254.202","192.168.254.203","192.168.254.204","192.168.254.205","192.168.254.206","192.168.254.207","192.168.254.208"],
      "worker_replicas": 1,
      "worker_flavors": {
        "memory_mb": "6128",
        "storage_gb": "32",
        "vcpu_count": "4"
      }
    }
  ]
}
```

## Set K8S mirror (cache) to avoid repository request limit
You can indicate in the creation request a list of mirrors to be used by the containerd. This is useful to avoid the limit of requests to the docker registry.
The mirrors are indicated in the `containerd_mirrors` field of the request. The key is the registry to be mirrored and the value is the mirror URL.

```
{
  "cni": "flannel",
  "pod_network_cidr": "10.254.0.0/16",
  "service_cidr": "10.200.0.0/16",
  "topology_onboard": true,
  "password": "abcdefgh",
  "containerd_mirrors": {
    "docker.io": "https://docker-registry.tnt-lab.unige.it/v2/cache/"
  },
  "ubuntu_version": "UBUNTU24",
  "require_port_security_disabled": true,
  "master_flavors": {
    "memory_mb": "4096",
    "storage_gb": "32",
    "vcpu_count": "4"
  },
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
			"additional_networks": ["data_paolo"],
      "load_balancer_pools_ips": [],
      "worker_replicas": 1,
      "worker_flavors": {
        "memory_mb": "4096",
        "storage_gb": "32",
        "vcpu_count": "4"
      }
    }
  ]
}
```

## Additional examples
You can find additional cluster creation examples [here](/blueprints/k8s/k8s_request_examples.md).
