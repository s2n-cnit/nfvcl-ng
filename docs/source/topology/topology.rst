====================
Topology description
====================

The Topology is the representation of the real topology on witch the NVFCL is going to deploy the Blueprints witch are
templates for NSs.
Everything that is contained in the Topology is used by the NFVCL to deploy Blueprints. For example, when a Blueprint is deploying
VMs, the VIM to be used is identified using the VIM data saved in the Topology.

The topology includes information about:

    - VIMs: this is a list of VIM used to deploy Virtual Machines. This item list should include networks NAMES that are
      present in the topology network list (VIM net are used to deploy VMs).
    - Networks: The list of networks available to the NFVCL. This list should include detailed information about networks
      included in every VIM in the topology collection.
    - Routers: list of Routers
    - PDUs: list of PDUs
    - K8s Clusters: The list of available K8S clusters to be used by the NFVCL. Some Blueprints use K8S to realize the NSs.
      All the k8s clusters deployed thought the use of NFVCL dedicated blueprint, are automatically added there.
    - Prometheus servers: This is a list of external Prometheus servers that can be used by the NVFCL when configuring
      node exportes that will send metrics.
