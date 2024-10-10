# Add and remove node from cluster

## Adding Nodes to the cluster

> This call is working only on K8S deployed using the Blueprint system, NOT on external clusters.

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
Make a DELETE request with the correct blueprint ID on
```
{{ base_url }}/nfvcl/v2/api/blue/k8s/del_workers?blue_id={{ID}}
```
And specify the names of the nodes to be removed in the body of the request
```json
{
  "node_names": [
    "uhhsa4_vm_w_0"
  ]
}
```
