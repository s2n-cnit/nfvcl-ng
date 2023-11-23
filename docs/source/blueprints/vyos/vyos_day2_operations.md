# Vyos blueprint day2 operations
## Step 1 - setup NAT rules
### 1 to 1 NAT
[[docs/images/nat_1-to1-schema.png]]
> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/VyOSBlue/{{ blue_id }}/1to1nat*
- Body:
```json
{
  "callbackURL": "",
  "operation": "1to1nat",
  "area": 0,
  "router_name": "8C1R3H_vyos_router_area_0_0",
  "rules": [
    {
      "inbound_network": "10.168.0.0/16",
      "virtual_ip": "8.8.8.8",
      "real_destination_ip": "10.170.3.9",
      "source_address": "10.170.3.9",
      "outbound_network": "10.168.0.0/16",
      "rule_number": 18,
      "description": "TEST"
    }
  ]
}
```

### SNAT
> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/VyOSBlue/{{ blue_id }}/snat*
- Body:
```json
{
  "callbackURL": "string",
  "operation": "snat",
  "area": 0,
  "router_name": "UYGZ8O_vyos_A0_0",
  "rules": [
    {
      "outbound_network": "10.203.21.0/24",
      "source_address": "192.168.27.0/24",
      "rule_number": 11,
      "description": "Radio_OSJDRI to Radio_test_paolo"
    }
  ]
}
```

### DNAT
> API (PUT): *{{ base_url }}/nfvcl/v1/api/blue/VyOSBlue/{{ blue_id }}/dnat*
- Body:
```json
{
  "callbackURL": "string",
  "operation": "dnat",
  "area": 0,
  "router_name": "8C1R3H_vyos_router_area_0_0",
  "rules": [
    {
      "inbound_network": "10.168.0.0/16",
      "virtual_ip": "7.7.7.7",
      "real_destination_ip": "10.170.3.9",
      "rule_number": 1,
      "description": ""
    }
  ]
}
```

## Step 2 - NAT rule deletion
> API (DELETE): *{{ base_url }}/nfvcl/v1/api/blue/VyOSBlue/{{ blue_id }}/nat*
- Body:
``` json
{
  "callbackURL": "string",
  "operation": "del_nat",
  "area": 0,
  "router_name": "8C1R3H_vyos_router_area_0_0",
  "rules": [
    1
  ]
}
```
