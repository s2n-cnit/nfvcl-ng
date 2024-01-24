# Kubernetes blueprint creation

`POST /nfvcl/v1/api/blue/K8sBlue`

Example request body:
```json
{
  "type": "K8sBlue",
  "config": {
    "version": "v1.28",
    "nfvo_onboard": "true",
    "cni": "flannel",
    "network_endpoints": {
      "mgt": "dmz-internal", 
      "data_nets": [
        {
          "mode": "layer2",
          "net_name": "data-net",
          "range_length": 20
        }
      ]
    }
  },
  "areas": [
    {
      "id": 1,
      "core": true,
      "workers_replica": 1
    }
  ]
}
```
If `nfvo_onboard` is true the Kubernetes cluster created with this blueprint will be added to the topologies in NFVCL
and OSM allowing other blueprint to be deployed on it.

In `network_endpoints` replace the network names with the ones in OpenStack, these names need to be the same of the onboarded
OpenStack topology.

The `areas` contains an object with these fields:
- `id`: ID of the area in which this cluster will be deployed (need to be one of the IDs present in the topology `vims[0].areas` list)
- `workers_replica`: How many worker need to be created
