# Kubernetes Blueprint
The Kubernetes Blueprint is dedicated to the lifecicle management of a K8S cluster (creation, deletion,
add node, install K8S plugins).

It acts on the required VIM to create a variable number of Virtual Machines on witch K8S software is configured.
One of these VMs acts as the cluster controller while the others act as workers.

The request of the creations contains important details like the network to be used by the load balancer.
See [Deployment](#deployment)

The Blueprint dedicated APIs base url is `{{ base_url }}/nfvcl/v2/api/blue/k8s`

## Deployment
To deploy the K8S Blueprint V2 you will need to perform a POST request on:
```
{{ base_url }}/nfvcl/v2/api/blue/k8s
```
This POST request body contains a lot of optional parameters as you can see looking to models in the exposed [Swagger](#TODO).

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

Here you can see a simple request (with no optional data) that is deploying a K8S cluster in the `area=3` (the VIM should be present in the Topology).
One and only one Core area must be always present! You can choose where the master node should be deployed. 
Using the worker_replicas parameter you can choose how many workers will be deployed in that area.

The NFVCL should support deployment over different VIMs of the same K8S cluster, nodes must have MGT connectivity between them.
Service Net is used by the MetalLb to expose services, possibly on a network that is reachable by the outside.
For a more detailed description of service network look at the following picture:

TODO
.. image:: ../../../images/k8s/k8s_blueprint-LB_assignment.drawio.svg
  :width: 400
  :alt: Service Net in K8S clusters
  :align: center


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
