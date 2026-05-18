# PacketRusher Blueprint

The PacketRusher blueprint allows for the deployment and management of PacketRusher, a high-performance UEFI and gNB simulator for 5G core networks.

## Creation

To instantiate a PacketRusher blueprint, send a POST request with the following JSON structure:

### Request Body (Creation)

```json
{
  "config": {
    "network_endpoints": {
      "mgt": "CTE-control",
      "n2": "CTE-control",
      "n3": "CTE-control"
    }
  },
  "areas": [
    {
      "id": 3,
      "sims": [
        {
          "imsi": "001011000000001",
          "plmn": "00101",
          "key": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
          "op": "112233445566778899AABBCCDDEEFF00",
          "opType": "OPC",
          "amf": 0,
          "configured_nssai": [
            {
              "sst": 1,
              "sd": "000001"
            }
          ],
          "default_nssai": [
            {
              "sst": 1,
              "sd": "000001"
            }
          ],
          "sessions": [
            {
              "type": "IPv4",
              "dnn": "internet",
              "slice": {
                "sst": 1,
                "sd": "000001"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Parameters

- `config.network_endpoints`:
    - `mgt`: (String) Management network name.
    - `n2`: (String) N2 control plane network name.
    - `n3`: (String) N3 data plane network name.
- `areas`: List of area objects.
    - `id`: (Integer) Area identifier (used as TAC).
    - `sims`: List of SIM configurations.
        - `imsi`: (String) IMSI of the UE.
        - `plmn`: (String) PLMN ID.
        - `key`: (String) Secret key (K).
        - `op`: (String) Operator code (OP or OPC).
        - `opType`: (String) Type of operator code, e.g., "OPC".
        - `amf`: (Integer, optional) AMF identifier.
        - `configured_nssai`: (List of Slices) Configured NSSAI.
            - `sst`: (Integer) Slice/Service Type.
            - `sd`: (String) Slice Differentiator.
        - `default_nssai`: (List of Slices) Default NSSAI.
        - `sessions`: (List of Sessions) PDU Sessions to establish.
            - `type`: (String) PDU Session type (e.g., "IPv4").
            - `dnn`: (String) Data Network Name (e.g., "internet").
            - `slice`: (Slice) Slice for this session.

---

## Day-2 Operations

These operations can be performed on an existing blueprint instance.

### Add Area (`/add_area`)

Adds a new area (VM) to the blueprint.

**POST** `/add_area`

```json
{
  "area_id": "4"
}
```

### Delete Area (`/del_area`)

Removes an area from the blueprint.

**DELETE** `/del_area`

```json
{
  "area_id": "4"
}
```

### Configure gNB (`/configure_gnb`)

Configures the gNB for a specific area. This step is required to start the simulation services on the VM.

**POST** `/configure_gnb`

```json
{
  "area": 3,
  "plmn": "00101",
  "tac": 3,
  "gnb_id": 1,
  "amf_ip": "10.0.0.10",
  "upf_ip": "10.0.0.20",
  "amf_port": 38412,
  "nssai": [
    {
      "sst": 1,
      "sd": "000001"
    }
  ],
  "additional_routes": [
    {
      "network_cidr": "10.10.10.0/24",
      "next_hop": "10.0.0.1"
    }
  ]
}
```

### Detach gNB (`/detach_gnb`)

Stops the simulation services in a specific area.

**POST** `/detach_gnb`

```json
{
  "area": 3
}
```

### Add SIM (`/add_sim`)

Adds a new SIM to an area.

**POST** `/add_sim`

```json
{
  "area_id": "3",
  "sim": {
    "imsi": "001011000000002",
    "plmn": "00101",
    "key": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
    "op": "112233445566778899AABBCCDDEEFF00",
    "opType": "OPC",
    "amf": 0,
    "configured_nssai": [{"sst": 1, "sd": "000001"}],
    "default_nssai": [{"sst": 1, "sd": "000001"}],
    "sessions": [
      {
        "type": "IPv4",
        "dnn": "internet",
        "slice": {"sst": 1, "sd": "000001"}
      }
    ]
  }
}
```

### Delete SIM (`/del_sim`)

Removes a SIM from an area.

**DELETE** `/del_sim`

```json
{
  "area_id": "3",
  "imsi": "001011000000002"
}
```
