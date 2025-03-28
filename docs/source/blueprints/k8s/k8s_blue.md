# K8S Blueprint
## What is this Blueprint for?
The Kubernetes Blueprint is dedicated to the lifecycle management of a K8S cluster.
It acts on the required VIMs to create a variable number of Virtual Machines on witch K8S software is configured.
One of these VMs acts as the cluster controller while the others act as workers. Based on the request some nodes of the 
cluster can be deployed in an area or in another (multi vim deployment)

The supported features are:
- Creation of a K8S cluster with the desired number of nodes (min 2, 1 controller and 1 worker). On creation you can:
    - Change the CNI between Flannel and Calico
    - Change the pod network CIDR and the service CIDR
    - Define if the cluster should be onboarded in the Topology
    - Choose the password for the VMs
    - Choose if the plugins should be installed
    - Choose if the port security should be disabled
    - Define the flavors for the master and the worker nodes
    - Define the management network and additional networks for the nodes
    - Define the load balancer pools IPs
    - Define the number of worker replicas
    - Define the containerd mirrors (or cache) to be used
- Destruction of the K8S cluster (done when destroying the blueprint instance)
- Add a node to the cluster of an existing K8S blueprint instance
- Delete a node from the cluster of an existing K8S blueprint instance (a controller and a worker must always be present)
- Installation of K8S plugins to a K8S blueprint instance

N.B
You can then manage a cluster created using the K8S blueprint, and onboarded in the Topology, using the [K8S utils](/kubernetes/k8s_man_index.rst)

The Blueprint dedicated APIs base url is `{{ base_url }}/nfvcl/v2/api/blue/k8s`

## Creation of a cluster using the blueprint
The creation consists of an API call, you can find examples and description of parameters [here](/blueprints/k8s/k8s_blue_creation.md)

## Destruction of a cluster created with a blueprint

List blueprints with GET on `/nfvcl/v2/api/blue/`

Find the correct one to be deleted and copy the `ID`.

Call the general blueprint delete API providing the ID with a DELETE on `/nfvcl/v2/api/blue/{{ID}}`

## Add and remove a node
To add or remove a node from a K8S cluster deployed using blueprint see [here](/blueprints/k8s/k8s_blue_add_del_node.md).

## Installing plugins
To install a plugin on K8S cluster deployed using blueprint see the K8S management part (not relative to blueprint) [here](/k8s/k8s_blue_plugin.md)
