# 5G Core Blueprint creation and usage

In this page there is described how to deploy and use a 5G Core blueprint.

The 5G Core blueprints supported by NFVCL have the same creation and DAY2 interface, for details regarding
a specific core check the following pages:
- [SD-Core Blueprint](../../ueransim/ueransim_blue_creation.md)
- [OpenAirInterface Blueprint](../../ueransim/ueransim_blue_creation.md)

## Requirements

> ⚠️ **Check the requirements carefully**

- Having a K8s cluster that is added to the NFVCL topology.
  Check [Onboarding external K8S Cluster](../../../topology/topology_nfvcl_k8s_onboarding.md) for more info on adding an
  external cluster or [Kubernetes Blueprint](../../k8s/k8s_blue_creation.md) to deploy a new cluster automatically
  onboarded by NFVCL.
- Having a gNB running for every area that will be added to the core. The PDU for the gNB need to be present in the topology, see TODO. A simulated gNB + UE can be deployed through the [UERANSIM Blueprint](../../ueransim/ueransim_blue_creation.md) and will be automatically added to the PDUs.
- Use kubectl to ensure that Metallb (or other load balancer) **have sufficient IPs** in the address pool to support
  the 5G Core chart deployment (one IP for each LoadBalancer service deployed by the blueprint).
  ```
  kubectl get ipaddresspool -A
  ```

## Deployment

> ⚠️ At the moment of writing, there is no implemented method to show the deployment
> status. So the user must remember which
> operations he performed (slices, areas, users added/deleted). The consistency
> is not guaranteed.

In the following example `{{ blueprint_type }}` need to be replaced with the type of the blueprint that you want to deploy, for example:
- sdcore
- OpenAirInterface

> API (POST): *{{ base_url }}/nfvcl/v2/api/blue/{{ blueprint_type }}*

```json
{
   "config":{
      "network_endpoints":{
         "mgt":"dmz-internal",
         "wan":"alderico-net",
         "n3":"n3",
         "n6":"n6",
         "data_nets":[
            {
               "net_name":"internet",
               "dnn":"internet",
               "dns":"8.8.8.8",
               "pools":[{"cidr":"10.250.0.0/16"}],
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
            "imsi":"001014000000002",
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
  - `mgt` is the management network.
  - `wan` is the network on which the K8s load balancer will assign the addresses to the core components.
  - `n3` the N3 network for UPF <-> gNB connection.
  - `n6` the N6 network for UPF <-> internet connection.
- The `dnn` and `net_name` fields in `data_nets` section can be chosen as desired, but it must be the same for both.
  Furthermore, when you create a UERANSIM blueprint you must set the field `apn` equal to `dnn` and `net_name` value.
- Dnn `cidrs` must not overlap.

Example payload for two areas, two slice and two subscribers.

```json
{
   "config":{
      "network_endpoints":{
         "mgt":"dmz-internal",
         "wan":"alderico-net",
         "n3":"n3",
         "n6":"n6",
         "data_nets":[
            {
               "net_name":"internet",
               "dnn":"internet",
               "dns":"8.8.8.8",
               "pools":[{"cidr":"10.250.0.0/16"}],
               "uplinkAmbr":"100 Mbps",
               "downlinkAmbr":"100 Mbps",
               "default5qi":"9"
            },
            {
               "net_name":"tim",
               "dnn":"tim",
               "dns":"8.8.8.8",
               "pools":[{"cidr":"10.251.0.0/16"}],
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
            "imsi":"001014000000002",
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
            "imsi":"001014000000003",
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
         "nci":"0x00000000",
         "idLength":32,
         "core":true,
         "slices":[
            {
               "sliceType":"EMBB",
               "sliceId":"000001"
            }
         ]
      },
      {
         "id":1,
         "nci":"0x00000001",
         "idLength":32,
         "core":false,
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
