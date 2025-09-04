from nfvcl_models.blueprint_ng.router_5g.router5gK8s import Router5GK8s

default_sdcore_routerk8s_config: Router5GK8s = Router5GK8s.model_validate(
    {
        "config": {
            "router": {
                "deploy": True,
                "cni": "macvlan",
                "resourceName": "intel.com/intel_sriov_netdevice",
                "routes": [
                    # {
                    #     "to": "10.250.0.0/16",
                    #     "via": "10.164.255.39"
                    # }
                ],
                "interfaces": [
                    # {
                    #     "name": "core",
                    #     "ip": "10.164.0.1/16",
                    #     "iface": "ens9"
                    # },
                    # {
                    #     "name": "access",
                    #     "ip": "10.163.0.1/16",
                    #     "iface": "ens9"
                    # },
                    # {
                    #     "name": "ran",
                    #     "ip": "10.180.0.1/16",
                    #     "iface": "ens9"
                    # }
                ]
            }
        }
    }
)
