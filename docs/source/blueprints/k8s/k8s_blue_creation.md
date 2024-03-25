# Kubernetes Blueprint
In this page you will find everything related to the K8S blueprint NG (or v2). The Blueprint dedicated APIs can be found at 
`{{ base_url }}/nfvcl/v2/api/blue/k8s`

## Deployment
To deploy the K8S Blueprint V2 you will need to call the POST API on:
```
{{ base_url }}/nfvcl/v2/api/blue/k8s
```

The body of the request should be a JSON, the entire body structure and options can be found in the swagger (A lot of
parameters are not needed since they have a default value).

Here you can see a simple request that is deploying a K8S cluster in the area=3 (the VIM should be present in the Topology).
One and only one Core area must be always present, you can choose where the Master Node should be deployed. Using the worker_replicas
parameter you can choose how many workers will be deployed in that area.

The NFVCL should support deployment over different VIMs of the same K8S cluster, nodes must have MGT connectivity between them.
Service Net is used by the MetalLb to expose services to the external.
```json
{
  "areas": [
    {
      "area_id": 3,
      "is_master_area": true,
      "mgmt_net": "dmz-internal",
      "service_net": "data_paolo",
      "service_net_required_ip_number": 20,
      "worker_replicas": 1
    }
  ]
}
```

### Plugin installation


## Adding Nodes to the cluster
> This call is working only on K8S deployed using the Blueprint system, NOT on external clusters.
{.is-warning}

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
      "area_id": 3,
      "is_master_area": false,
      "mgmt_net": "dmz-internal",
      "service_net": "data_paolo",
      "worker_replicas": 1
    }
  ]
}
```
Note that master area has been set to FALSE cause the master has been already deployed.

## Removing Nodes from the cluster
!!! Still to be implemented.
