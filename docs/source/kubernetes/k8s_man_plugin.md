### Plugin installation
The plugin installation can be performed on any K8S cluster onboarded in the Topology (generated from the K8S blueprint or added as an external cluster).
Make a POST using the **Topology** cluster ID on:
```
http://192.168.254.11:5002/k8s/{CLUSTER_ID_TOPOLOGY}/plugins
```
Inserting in the body the information required for the installation of plugins such as the plugin list and the data for the 
plugin installation:
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
