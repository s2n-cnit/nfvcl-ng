# K8S Blueprint request examples

## Network cases
### Using mgt net to expose services
```
{
  "password": "ubuntu",
  "require_port_security_disabled": true,
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "use_vxlan": false,
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1
    }
  ]
}
```

### Using secondary net to expose services
```
{
  "password": "ubuntu",
  "require_port_security_disabled": true,
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "service_net": "data_paolo",
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1
    }
  ]
}
```

### Using VXLAN to expose services
```
{
  "password": "ubuntu",
  "require_port_security_disabled": true,
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1
    }
  ]
}
```

## Flavors
### Use default flavors
```
{
  "password": "ubuntu",
  "require_port_security_disabled": true,
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1
    }
  ]
}
```

### Use a custom flavor
```
{
	"password": "ubuntu",
	"require_port_security_disabled": true,
  "master_flavors": {
    "vcpu_count": "4",
    "memory_mb": "4096",
    "storage_gb": "16",
    "vcpu_type": "host",
    "require_port_security_disabled": false
  },
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
			"service_net": "data_paolo",
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1,
			"worker_flavors": {
        "vcpu_count": "4",
        "memory_mb": "4096",
        "storage_gb": "32",
        "vcpu_type": "host",
        "require_port_security_disabled": false
      }
    }
  ]
}
```

### Use an existing flavor (use case: no permission to create it)
```
{
	"password": "ubuntu",
	"require_port_security_disabled": true,
  "master_flavors": {
    "vcpu_count": "4",
    "memory_mb": "4096",
    "storage_gb": "16",
    "vcpu_type": "host",
    "require_port_security_disabled": false
  },
  "areas": [
    {
      "area_id": 1,
      "is_master_area": true,
			"service_net": "data_paolo",
      "mgmt_net": "dmz-internal",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1,
			"worker_flavors": {
        "vcpu_count": "4",
        "memory_mb": "4096",
        "storage_gb": "32",
        "vcpu_type": "host",
        "require_port_security_disabled": false
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
