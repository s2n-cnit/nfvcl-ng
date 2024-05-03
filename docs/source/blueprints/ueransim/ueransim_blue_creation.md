# UERANSIM blueprint creation
To initialize a blueprint for UERanSim you can use the following dedicated call. If the blueprint is deployed to be connected to another
 blueprint, ensure that they are on the same network.
For example, if the K8S blueprint on witch a 5G Core is running, is connected to `dmz-internal` management network and to `data_paolo` data network, 
the blueprint should be deployed like follows. The `wan` network is the one used to reach the AMF component of the core (`N2`).

`POST /nfvcl/v2/api/blue/UeRanSim`
```json
{
    "type": "UeRanSim",
    "config": {
        "network_endpoints": {
            "mgt": "dmz-internal",
            "wan": "data_paolo"
        }
    },
    "areas": [
        {
            "id": 3,
            "nci": "0x00000002",
            "idLength": 32,
            "ues": [
                {
                    "id": 1,
                    "sims": [
                        {
                            "imsi": "001010000000002",
                            "plmn": "00101",
                            "key": "465B5CE8B199B49FAA5F0A2EE238A6BC",
                            "op": "E8ED289DEBA952E4283B54E88E6183CA",
                            "opType": "OPC",
                            "amf": "8000",
                            "configured_nssai": [{"sst": 1, "sd": 1}],
                            "default_nssai": [{"sst": 1, "sd": 1}],
                            "sessions": [
                                {
                                    "type": "IPv4",
                                    "apn": "internet2",
                                    "slice": {"sst": 1, "sd": 1}
                                }
                            ]
                        } 
                    ]
                }
            ]
        }
    ]
}
```
