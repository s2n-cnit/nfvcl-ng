# 5G Core Blueprint creation and usage

In this page there is described how to deploy and use a 5G Core blueprint.

The 5G Core blueprints supported by NFVCL have the same creation and DAY2 interface, for details regarding
a specific core check the following pages:
- [SD-Core Blueprint](../../ueransim/ueransim_blue_creation.md)
- [OpenAirInterface Blueprint](../../ueransim/ueransim_blue_creation.md)

```{image} ../../../images/blueprint/5g/Topology-5G.svg
:alt: 5G topology
:align: center
```

## Requirements

> ⚠️ **Check the requirements carefully**

- Having a K8s cluster that is added to the NFVCL topology.
  Check [Onboarding external K8S Cluster](../../../topology/topology_nfvcl_k8s_onboarding.md) for more info on adding an
  external cluster or [Kubernetes Blueprint](../../k8s/k8s_blue_creation.md) to deploy a new cluster automatically
  onboarded by NFVCL.
- (Optional) If you want NFVCL to configure automatically a (supported) gNB:
    - Having a gNB running for every area that will be added to the core. The PDU for the gNB need to be present in the topology, see [TODO]. 
      A simulated gNB + UE can be deployed through the [UERANSIM Blueprint](../../ueransim/ueransim_blue_creation.md) and will be automatically added to the PDUs.
- Use kubectl to ensure that Metallb (or other load balancer) **have sufficient IPs** in the address pool to support
  the 5G Core chart deployment (one IP for each LoadBalancer service deployed by the blueprint).
  ```
  kubectl get ipaddresspool -A
  ```
- The networks used in the blueprint must be present in the topology.
- To use Multus networks, the Multus CNI must be installed in the cluster.
- If Multus is used a pool of IPs must be available for the Multus networks, this pool need to be added to the network in the topology and assigned to the k8s cluster.

## Deployment

> ⚠️ At the moment of writing, there is no implemented method to show the deployment
> status. So the user must remember which
> operations he performed (slices, areas, users added/deleted). The consistency
> is not guaranteed.

In the following example `{{ blueprint_type }}`, **in the URL**, need to be replaced with the type of the blueprint that you want to deploy, for example:
- 'sdcore'
- 'oai'
- 'free5gc'

**The description of fields is after the body of the request!**

> API (POST): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}*

```json
{
   "config":{
      "network_endpoints":{
         "mgt":{
            "net_name":"dmz-internal"
         },
         "n2":{
            "net_name":"alderico-net",
            "type":"MULTUS"
         },
         "n4":{
            "net_name":"alderico-net",
            "type":"MULTUS"
         },
         "data_nets":[
            {
               "net_name":"internet",
               "dnn":"internet",
               "dns":"8.8.8.8",
               "pools":[
                  {
                     "cidr":"10.250.0.0/16"
                  }
               ],
               "uplinkAmbr":"100 Mbps",
               "downlinkAmbr":"100 Mbps",
               "default5qi":"9"
            }
         ]
      },
      "plmn":"00101",
      "sliceProfiles":[
         {
            "sliceId":"000001",
            "sliceType":"EMBB",
            "dnnList":[
               "internet"
            ],
            "profileParams":{
               "isolationLevel":"ISOLATION",
               "sliceAmbr":"1000 Mbps",
               "ueAmbr":"50 Mbps",
               "maximumNumberUE":10,
               "pduSessions":[
                  {
                     "pduSessionId":"0",
                     "pduSessionAmbr":"20 Mbps",
                     "flows":[
                        {
                           "flowId":"1",
                           "ipAddrFilter":"8.8.4.4",
                           "qi":"9",
                           "gfbr":"10 Mbps"
                        }
                     ]
                  }
               ]
            },
            "locationConstraints":[
               {
                  "geographicalAreaId":"1",
                  "tai":"00101000001"
               }
            ],
            "enabledUEList":[
               {
                  "ICCID":"*"
               }
            ]
         }
      ],
      "subscribers":[
         {
            "imsi":"001014000000001",
            "k":"814BCB2AEBDA557AEEF021BB21BEFE25",
            "opc":"9B5DA0D4EC1E2D091A6B47E3B91D2496",
            "authenticationMethod":"5G_AKA",
            "authenticationManagementField":"9001",
            "snssai":[
               {
                  "sliceId":"000001",
                  "sliceType":"EMBB",
                  "pduSessionIds":[
                     "0"
                  ],
                  "default_slice":true
               }
            ]
         }
      ]
   },
   "areas":[
      {
         "id":0,
         "nci":"0x00000005",
         "idLength":32,
         "core":true,
         "upf":{
            "type":"sdcore_upf"
         },
         "gnb":{
            "configure":true
         },
         "networks":{
            "n3":{
               "net_name":"alderico-n3",
               "type":"MULTUS"
            },
            "n6":{
               "net_name":"alderico-n6",
               "type":"MULTUS"
            },
            "gnb":{
               "net_name":"alderico-gnb"
            }
         },
         "slices":[
            {
               "sliceType":"EMBB",
               "sliceId":"000001"
            }
         ]
      }
   ]
}
```

- In the `network_endpoints` section:
  - `mgt` is the management network, used when the UPF/Router is a VM.
  - `n2` is the network used for AMF <-> gNB connection.
  - `n4` is the network used for SMF <-> UPF connection.
  - `n2` and `n4` can concide as networks, no internet connection is required, it can be the 'mgt' network if needed. Better to be a dedicated and isolated net.
Some networks have a `type` field, this is used to specify the network type, currently supported types are `MULTUS` and `LB` (LoadBalancer), the `type` field is ignored when the component is not deployed on k8s.
> ⚠️ Mixing the network types may not work.
> 
> Currently not all implementations support Multus, only `oai`


- The `dnn` and `net_name` fields in `data_nets` section can be chosen as desired, but it must be the same for both.
  Furthermore, when you create a UERANSIM blueprint you must set the field `apn` equal to `dnn` and `net_name` value.
- Dnn `cidrs` must not overlap.
- In the `areas` section for each are you need to set:
  - `upf.type`: the UPF implementation to deploy in this area, currently you can choose between:
    - `sdcore_upf`
    - `oai_upf`
    - `oai_upf_k8s`: This is the UPF implementation for the OAI blueprint deployed in a K8s cluster.
    - `free5gc_upf`
  
    **NFVCL will configure every Core and UPF combination but mixing the implementations may not work.**  
  - `networks`:
    - `n3`: The network to use for user plane data between gNB and UPF (going through the router)
    - `n6`: The network to use for user plane data between UPF and internet (going through the router)
    - `gnb`: The network between gNB and Router
    - `n3`, `n6` and `gnb`: They must be different (virtual) networks, some implementations require having dedicated interfaces that must not
       have the same address space.

For more details about the networks check 5G topology TODO

Example payload for two areas, two slice and two subscribers.

```json
{
   "config":{
      "network_endpoints":{
         "mgt":{
            "net_name":"dmz-internal"
         },
         "n2":{
            "net_name":"alderico-net",
            "type":"MULTUS"
         },
         "n4":{
            "net_name":"alderico-net",
            "type":"MULTUS"
         },
         "data_nets":[
            {
               "net_name":"internet",
               "dnn":"internet",
               "dns":"8.8.8.8",
               "pools":[
                  {
                     "cidr":"10.250.0.0/16"
                  }
               ],
               "uplinkAmbr":"100 Mbps",
               "downlinkAmbr":"100 Mbps",
               "default5qi":"9"
            },
            {
               "net_name":"tim",
               "dnn":"tim",
               "dns":"8.8.8.8",
               "pools":[
                  {
                     "cidr":"10.251.0.0/16"
                  }
               ],
               "uplinkAmbr":"100 Mbps",
               "downlinkAmbr":"100 Mbps",
               "default5qi":"9"
            }
         ]
      },
      "plmn":"00101",
      "sliceProfiles":[
         {
            "sliceId":"000001",
            "sliceType":"EMBB",
            "dnnList":[
               "internet"
            ],
            "profileParams":{
               "isolationLevel":"ISOLATION",
               "sliceAmbr":"1000 Mbps",
               "ueAmbr":"50 Mbps",
               "maximumNumberUE":10,
               "pduSessions":[
                  {
                     "pduSessionId":"0",
                     "pduSessionAmbr":"20 Mbps",
                     "flows":[
                        {
                           "flowId":"1",
                           "ipAddrFilter":"8.8.4.4",
                           "qi":"9",
                           "gfbr":"10 Mbps"
                        }
                     ]
                  }
               ]
            },
            "locationConstraints":[
               {
                  "geographicalAreaId":"1",
                  "tai":"00101000001"
               }
            ],
            "enabledUEList":[
               {
                  "ICCID":"*"
               }
            ]
         },
         {
            "sliceId":"000002",
            "sliceType":"EMBB",
            "dnnList":[
               "tim"
            ],
            "profileParams":{
               "isolationLevel":"ISOLATION",
               "sliceAmbr":"1000 Mbps",
               "ueAmbr":"50 Mbps",
               "maximumNumberUE":10,
               "pduSessions":[
                  {
                     "pduSessionId":"0",
                     "pduSessionAmbr":"20 Mbps",
                     "flows":[
                        {
                           "flowId":"1",
                           "ipAddrFilter":"8.8.4.4",
                           "qi":"9",
                           "gfbr":"10 Mbps"
                        }
                     ]
                  }
               ]
            },
            "locationConstraints":[
               {
                  "geographicalAreaId":"1",
                  "tai":"00101000001"
               }
            ],
            "enabledUEList":[
               {
                  "ICCID":"*"
               }
            ]
         }
      ],
      "subscribers":[
         {
            "imsi":"001014000000001",
            "k":"814BCB2AEBDA557AEEF021BB21BEFE25",
            "opc":"9B5DA0D4EC1E2D091A6B47E3B91D2496",
            "authenticationMethod":"5G_AKA",
            "authenticationManagementField":"9001",
            "snssai":[
               {
                  "sliceId":"000001",
                  "sliceType":"EMBB",
                  "pduSessionIds":[
                     "0"
                  ],
                  "default_slice":true
               }
            ]
         },
         {
            "imsi":"001014000000004",
            "k":"814BCB2AEBDA557AEEF021BB21BEFE25",
            "opc":"9B5DA0D4EC1E2D091A6B47E3B91D2496",
            "authenticationMethod":"5G_AKA",
            "authenticationManagementField":"9001",
            "snssai":[
               {
                  "sliceId":"000002",
                  "sliceType":"EMBB",
                  "pduSessionIds":[
                     "0"
                  ],
                  "default_slice":true
               }
            ]
         }
      ]
   },
   "areas":[
      {
         "id":0,
         "nci":"0x00000005",
         "idLength":32,
         "core":true,
         "upf":{
            "type":"sdcore_upf"
         },
         "networks":{
            "n3":{
               "net_name":"alderico-n3",
               "type":"MULTUS"
            },
            "n6":{
               "net_name":"alderico-n6",
               "type":"MULTUS"
            },
            "gnb":{
               "net_name":"alderico-gnb"
            }
         },
         "slices":[
            {
               "sliceType":"EMBB",
               "sliceId":"000001"
            }
         ]
      },
      {
         "id":1,
         "nci":"0x00000005",
         "idLength":32,
         "core":false,
         "upf":{
            "type":"sdcore_upf"
         },
         "networks":{
            "n3":{
               "net_name":"alderico-n3",
               "type":"MULTUS"
            },
            "n6":{
               "net_name":"alderico-n6",
               "type":"MULTUS"
            },
            "gnb":{
               "net_name":"alderico-gnb"
            }
         },
         "slices":[
            {
               "sliceType":"EMBB",
               "sliceId":"000002"
            }
         ]
      }
   ]
}
```

Every blueprint is identified by ID, given during creation. You can check blueprints IDs calling:

> API (GET): *{{ base_url }}/nfvcl/v2/api/blue/*

Blueprint ID will be necessary to call api on the core.

## Add Slice

There are 2 variant of the `add_slice` API:
- `add_slice_oss`: The `area_ids` field is mandatory
- `add_slice_operator`: The `area_ids` field is optional, the slice can be added before adding the area.

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/add_slice_oss?blue_id={{ blue_id }}*

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/add_slice_operator?blue_id={{ blue_id }}*

```json
{
  "area_ids": ["1"],
  "sliceId": "000002",
  "sliceType": "EMBB",
  "dnnList": [
    "dnn2"
  ],
  "profileParams": {
    "isolationLevel": "ISOLATION",
    "sliceAmbr": "1000 Mbps",
    "ueAmbr": "50 Mbps",
    "maximumNumberUE": 10,
    "pduSessions": [
      {
        "pduSessionId": "1",
        "pduSessionAmbr": "20 Mbps",
        "flows": [
          {
            "flowId": "1",
            "ipAddrFilter": "8.8.4.4",
            "qi": "9",
            "gfbr": "10 Mbps"
          }
        ]
      }
    ]
  },
  "locationConstraints": [
    {
      "geographicalAreaId": "1",
      "tai": "00101000001"
    }
  ],
  "enabledUEList": [
    {
      "ICCID": "*"
    }
  ]
}
```

The `area_ids` field is a list of areas on which this slice will be added, use `["*"]` to add the slice to every area.

## Del Slice

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/del_slice?blue_id={{ blue_id }}*

```json
{
  "sliceId": "000002"
}
```

When you delete a slice the subscriber and his session management associated with that slice will be automatically 
removed from DB.

## Add Tac

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/add_tac?blue_id={{ blue_id }}*

```json
{
  "id": 1,
  "nci": "0x00000003",
  "idLength": 32,
  "core": false,
  "slices": [
    {
      "sliceType": "EMBB",
      "sliceId": "000002"
    }
  ]
}
```

- Id: area id, must be a valid id defined during topology creation.
- Slices: list of slice that area will support.

Before add a tac, slice must be added to core, because slice information will be read from *sliceProfiles* of [initial
payload](#Deployment).

## Del Tac

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/del_tac?blue_id={{ blue_id }}*

```json
{
  "areaId": 1
}
```

- Id: area id, must be a valid id defined during topology and already deployed area.

## Add Subscriber

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/add_subscriber?blue_id={{ blue_id }}*

```json
{
  "imsi": "001014000000003",
  "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
  "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
  "authenticationMethod": "5G_AKA",
  "authenticationManagementField": "9001",
  "snssai": [
    {
      "sliceId": "000002",
      "sliceType": "EMBB",
      "pduSessionIds": [
        "1"
      ],
      "default_slice": true
    }
  ]
}
```

When you create a new subscriber also his session management subscription data with the slice in 
the payload will be created.

## Del Subscriber

> API (PUT): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}/del_subscriber?blue_id={{ blue_id }}*

```json
{
  "imsi": "001014000000003"
}
```

When you delete a subscriber also his session management subscription data will be deleted.
