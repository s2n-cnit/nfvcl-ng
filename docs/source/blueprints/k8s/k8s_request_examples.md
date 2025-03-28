# K8S Blueprint request examples

## Multi AREA deployment and custom flavors
```
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
    "vcpu_count": "6"
  },
  "areas": [
    {
      "area_id": 1,
      "is_master_area": false,
      "mgmt_net": "6GREEN-control",
      "load_balancer_pools_ips": ["192.168.131.241","192.168.131.242","192.168.131.243","192.168.131.244","192.168.131.246","192.168.131.248","192.168.131.249"],
      "worker_replicas": 1,
      "worker_flavors": {
        "memory_mb": "6128",
        "storage_gb": "32",
        "vcpu_count": "6"
      }
    },
		{
      "area_id": 2,
      "is_master_area": false,
      "mgmt_net": "CTE-control",
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

## Add a K8S node to an existing cluster
Make sure you have added the cluster ID (Blueprint ID) as query parameter

http://NFVCL_IP:5002/nfvcl/v2/api/blue/k8s/add_node?blue_id=ITPHY8

```
{
  "areas": [
    {
      "area_id": 1,
      "is_master_area": false,
      "mgmt_net": "dmz-internal",
      "worker_replicas": 1
    }
  ]
}
```

## Remove a node from an existing cluster
Make sure you have added the cluster ID (Blueprint ID) as query parameter
http://NFVCL_IP:5002/nfvcl/v2/api/blue/k8s/del_workers?blue_id=Z0AOU1
And then the list of nodes to remove:

```
{
  "node_names": [
    "XLQ4H2_VM_W_1"
  ]
}
```

## Install additional plugins
Refer to [Install Plugins](/kubernetes/k8s_man_apis_example#Plugin installation)
