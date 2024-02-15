# Free5GC Blueprint creation
In this page there is described how to deploy a Free5GC blueprint.

## Requirements
> ⚠️ **Check the requirements carefully**


- Having a K8s cluster that is **onboarded** on the NFVO (OSM). Check [Onboarding external K8S Cluster](Onboarding-external-K8S-Cluster) for more info on adding an external cluster or [Kubernetes Blueprint](Kubernetes-Blueprint) to deploy a new cluster automatically onboarded by NFVCL.
  The cluster must be connected to a `mgt` and `data` network.
- Having a gNB running, it can be deployed through UERANSIM blueprint. See [UERANSIM Blueprint](UERANSIM-Blueprint) for more information. Use the same `mgt` and `data` network of the previous point.
- Add collection 'pnf' in the NFVCL mongo database with the following content 
  ```
  {
      "_id": {
          "$oid": "6384cfd95f2308370ca82f0d"
      },
      "type": "ueransim_nb",
      "vnfd": "ueransim_nb_XXX_pnfd",
      "name": "Configurator_UeRanSimNB",
      "module": "blueprints.blue_5g_base.configurators.ueransim_nb_configurator"
  }
  ```
- Use kubectl to ensure that Metallb (or other load balancer) **have sufficient IPs** in the address pool to support Free5GC chart deployment (one IP for each pod deployed from the blueprint).
  ```
  kubectl get ipaddresspool -A
  ```
- Having onboarded the helm chart on OSM with the following POST on `http://NFVCL_IP:5002/helm_repo/`
	```
  {
  "name": "free5gc",
  "description": "free5gc 3.2.0",
  "version": "3.2.0"
	}
  ```

## Deployment
`POST /nfvcl/v1/api/blue/Free5GC_K8s`

```json
{
  "type": "Free5GC_K8s",
  "config": {
    "network_endpoints": {
      "mgt": "dmz-internal",
      "wan": "dmz-internal",
      "data_nets": [
        {
          "net_name": "radio_PQOUQB", # Replace with the name of the network created by the UERANSIM blueprint
          "dnn": "radio_PQOUQB", # Replace with the name of the network created by the UERANSIM blueprint
          "dns": "8.8.8.8", 
          "pools": [{"cidr": "10.168.0.0/16"}],
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
        "dnnList": ["radio_PQOUQB"], # Replace with the name of the network created by the UERANSIM blueprint
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
      "id": 0, # Deployment area ID
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
      "id": 1, # The area of the gNB (Need to be the same of the deployed UERANSIM blueprint)
      "nci": "0x00000003",
      "idLength": 32,
      "core": false,
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
