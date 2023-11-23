# UERANSIM blueprint creation

`POST /nfvcl/v1/api/blue/UeRanSim`
```json
{
    "type": "UeRanSim",
    "config": {
        "network_endpoints": {
            "mgt": "dmz-internal",
            "wan": "dmz-internal"
        }
    },
    "areas": [
        {
            "id": 1,
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
