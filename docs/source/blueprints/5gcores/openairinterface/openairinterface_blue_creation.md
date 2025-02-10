# OpenAirInterface Blueprint creation and usage

> ⚠️ **This page is WIP, check the generic 5G deployment one**

In this page there is described how to deploy and use OpenAirInterface blueprint.

## Requirements

> ⚠️ **Check the requirements carefully**

- Having a K8s cluster that is **onboarded** on the NFVO (OSM).
  Check [Onboarding external K8S Cluster](../../../topology/topology_nfvcl_k8s_onboarding.md) for more info on adding an
  external cluster or [Kubernetes Blueprint](../../k8s/k8s_blue_creation.md) to deploy a new cluster automatically
  onboarded by NFVCL.
- Having a gNB running, it can be deployed through UERANSIM blueprint.
  See [UERANSIM Blueprint](../../ueransim/ueransim_blue_creation.md) for more information.

- Use kubectl to ensure that Metallb (or other load balancer) **have sufficient IPs** in the address pool to support
  OpenAirInterface chart deployment (one IP for each pod deployed from the blueprint).
  ```
  kubectl get ipaddresspool -A
  ```

## Deployment

> ⚠️ At the moment of writing, there is no implemented method to show the deployment
> status. So the user must remember which
> operations he performed (slices, areas, users added/deleted). The consistency
> is not guaranteed.

This payload deploys the core and a single upf.

> API (POST): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface*

```json
{
  "type": "OpenAirInterface",
  "config": {
    "network_endpoints": {
      "mgt": "dmz-internal",
      "wan": "davide-net",
      "data_nets": [
        {
          "net_name": "dnn1",
          "dnn": "dnn1",
          "dns": "8.8.8.8",
          "pools": [
            {
              "cidr": "12.168.0.0/16"
            }
          ],
          "uplinkAmbr": "100 Mbps",
          "downlinkAmbr": "100 Mbps",
          "default5qi": "9"
        },
        {
          "net_name": "dnn2",
          "dnn": "dnn2",
          "dns": "8.8.8.8",
          "pools": [
            {
              "cidr": "13.168.0.0/16"
            }
          ],
          "uplinkAmbr": "100 Mbps",
          "downlinkAmbr": "100 Mbps",
          "default5qi": "9"
        }
      ]
    },
    "plmn": "00101",
    "sliceProfiles": [
      {
        "sliceId": "000001",
        "sliceType": "EMBB",
        "dnnList": [
          "dnn1"
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
    ],
    "subscribers": [
      {
        "imsi": "001014000000002",
        "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
        "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
        "authenticationMethod": "5G_AKA",
        "authenticationManagementField": "9001",
        "snssai": [
          {
            "sliceId": "000001",
            "sliceType": "EMBB",
            "pduSessionIds": [
              "1"
            ],
            "default_slice": true
          }
        ]
      }
    ]
  },
  "areas": [
    {
      "id": 0,
      "nci": "0x00000005",
      "idLength": 32,
      "core": true,
      "slices": [
        {
          "sliceType": "EMBB",
          "sliceId": "000001"
        }
      ]
    }
  ]
}
```

- The *wan* field in the *network_endpoints* section represents a secondary network that must be created on Openstack.
  This blueprint supports a multi upf deployment for a single core.
  If you want to create a core with multiple upf you have to define more area in *areas*. Pay attention, the new area
  have to be defined in the topology too. Every upf required a deployment of a UERANSIM blueprint.
- The *dnn* and *net_name* fields in *data_nets* section can be chosen as desired, but it must be the same for both.
  Furthermore, when you create a UERANSIM blueprint you must set the field *apn* equal to *dnn* and *net_name* value.
- Dnn *cidrs* must not overlap.

Example payload for two areas, two slice and two subscribers.

```json
{
  "type": "OpenAirInterface",
  "config": {
    "network_endpoints": {
      "mgt": "dmz-internal",
      "wan": "davide-net",
      "data_nets": [
        {
          "net_name": "dnn1",
          "dnn": "dnn1",
          "dns": "8.8.8.8",
          "pools": [
            {
              "cidr": "12.168.0.0/16"
            }
          ],
          "uplinkAmbr": "100 Mbps",
          "downlinkAmbr": "100 Mbps",
          "default5qi": "9"
        },
        {
          "net_name": "dnn2",
          "dnn": "dnn2",
          "dns": "8.8.8.8",
          "pools": [
            {
              "cidr": "13.168.0.0/16"
            }
          ],
          "uplinkAmbr": "100 Mbps",
          "downlinkAmbr": "100 Mbps",
          "default5qi": "9"
        }
      ]
    },
    "plmn": "00101",
    "sliceProfiles": [
      {
        "sliceId": "000001",
        "sliceType": "EMBB",
        "dnnList": [
          "dnn1"
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
      },
      {
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
    ],
    "subscribers": [
      {
        "imsi": "001014000000002",
        "k": "814BCB2AEBDA557AEEF021BB21BEFE25",
        "opc": "9B5DA0D4EC1E2D091A6B47E3B91D2496",
        "authenticationMethod": "5G_AKA",
        "authenticationManagementField": "9001",
        "snssai": [
          {
            "sliceId": "000001",
            "sliceType": "EMBB",
            "pduSessionIds": [
              "1"
            ],
            "default_slice": true
          }
        ]
      },
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
    ]
  },
  "areas": [
    {
      "id": 0,
      "nci": "0x00000005",
      "idLength": 32,
      "core": true,
      "slices": [
        {
          "sliceType": "EMBB",
          "sliceId": "000001"
        }
      ]
    },
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
  ]
}
```

Every blueprint is identified by ID, given during creation. You can check blueprints IDs calling:

> API (GET): *{{ base_url }}/nfvcl/v1/api/blue/*

It will give a list of blueprint, every item of the list has a field *type*, look for the one with value 
*OpenAirInterface*.

Blueprint ID will be necessary to call api on the core.

## Add Slice

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/add_slice*

```json
{
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
  ],
  "type": "OpenAirInterface",
  "operation": "add_slice",
  "area_id": 0
}
```

> ⚠️ If you specify last field *area_id*, core and upf will be restarted and configured to
> support new slice, if you remove it from payload, the slice will be only added to *sliceProfiles* of 
> [initial payload](#Deployment). The reason behind this implementation choice is that creating an area and a subscriber
> requires the slice data to already be present in *sliceProfiles*. Therefore, before creating a subscriber or an area 
> it is necessary to add the slice to specify its data.

This blueprint support only one *PLMN*, this means that a subscriber can be associated to only one slice.
If you want an already defined subscriber to be associated to another slice you have to delete and re-add the
subscriber with desire slice.

## Del Slice

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/del_slice*

```json
{
  "type": "OpenAirInterface",
  "operation": "del_slice",
  "sliceId": "000002"
}
```

When you delete a slice the subscriber and his session management associated with that slice will be automatically 
removed from DB.

## Add Tac

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/add_tac*

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
  ],
  "type": "OpenAirInterface",
  "operation": "add_tac"
}
```

- Id: area id, must be a valid id defined during topology creation.
- Slices: list of slice that area will support.

Before add a tac, slice must be added to core, because slice information will be read from *sliceProfiles* of [initial
payload](#Deployment).

## Del Tac

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/del_tac*

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
  ],
  "type": "OpenAirInterface",
  "operation": "del_tac"
}
```

- Id: area id, must be a valid id defined during topology and already deployed area.
- Slices: list of slice that area will support.

## Add Subscriber

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/add_subscriber*

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
  ],
  "type": "OpenAirInterface",
  "operation": "add_ues"
}
```

When you create a new subscriber also his session management subscription data with the slice in 
the payload will be created.

## Del Subscriber

> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/OpenAirInterface/{blue_id}/del_subscriber*

```json
{
  "type": "OpenAirInterface",
  "operation": "del_ues",
  "imsi": "001014000000003"
}
```

When you delete a subscriber also his session management subscription data will be deleted.

## Usage

Once the blueprint has been created, if you want to test it, you need to connect to the two VMs created by 
the UERANSIM blueprint. To do is, you have to associate a floating ip to the VMs then connect to them.
Once you prompt to the console you have to disable the screen created by default from blueprint from both the VMs
(in the future we will remove the screen creation). 
To remove screen:

- `screen -r`
- `ctrl + c`

Then you have to run:

- `UERANSIM/build/nr-gnb -c nb.cfg` on gNB Vm.
- `UERANSIM/build/nr-ue -c sim_0.yaml` on ue Vm.

Once the UE is connected an output will be provided to the console. The last line contains the name of a new interface
created by UERANSIM.
Copy the interface name, open another console (on one of the two VMs, it doesn't matter which one), and type:

- `chmod +x UERANSIM/build/nr-binder` to give execution permission to file (to do only once).
- `cd UERANSIM/build/`
- `./nr-binder {interface_name} bash `

Now the traffic will be passed through 5G core. To test it:

- `wget http://ipv4.download.thinkbroadband.com/1GB.zip` to download 1GB file and test speed.

To stop the binding, just type:
 
- `exit`
