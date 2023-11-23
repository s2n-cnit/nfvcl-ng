# Vyos Blueprint creation
## Build Vyos image
It is necessary to build directly the Vyos image because the default one is missing some functionalities like DHCP and 
Cloud-init.To build a VyOS image you can use the following instructions. For additional functionalities look at the 
[GitHub](https://github.com/vyos) official page.

```console
cd

wget https://s3-us.vyos.io/1.2.9/vyos-1.2.9-amd64.iso

sudo apt update

sudo apt install -y ansible python3

git clone https://github.com/vyos/vyos-vm-images

cd vyos-vm-images

sudo ansible-playbook qemu.yml -e cloud_init=true -e enable_dhcp=true -e iso_local=/home/ubuntu/vyos-1.2.9-amd64.iso -e keep_user=true -e enable_ssh=true
```

> Result should be located in **/tmp**

# Blueprint API usage
## Step 0 - Vyos Creation
> API (POST): *{{ base_url }}/nfvcl/v1/api/blue/VyOSBlue*

- BODY:
```json
{
  "type": "VyOSBlue",
  "areas": [
    {
      "id": 0,
      "config_list": [
        {
          "version": "1.00",
          "admin_password": "vyos",
          "network_endpoints": {
            "mgt": {
              "net_name": "control-os1"
            },
            "data_nets": [
              {
                "net_name": "radio"
              }
            ]
          }
        }
      ]
    }
  ]
}
```
The password can be omitted and by default it's value is ***vyos***.

### VyOS status after creation
An example of VyOS's status after creation should result like this:
```json
"conf":{
    "type": "VyOSBlue",
    "callbackURL": null,
    "areas": [
      {
        "id": 0,
        "config_list": [
          {
            "version": "1.00",
            "name": "K2ZSWQ_vyos_router_area_0_0",
            "nsd_name": "K2ZSWQ_vyos_router_area_0_0",
            "nsd_id": "926454e0-4a79-438d-ae18-9eabd78bd517",
            "network_endpoints": {
              "mgt": {
                "net_name": "mngn-vnf-os",
                "interface_name": "eth0",
                "osm_interface_name": null,
                "ip_addr": "192.168.13.82",
                "network": "192.168.13.0/24"
              },
              "data_nets": [
                {
                  "net_name": "radio_0SJDRI",
                  "interface_name": "eth1",
                  "osm_interface_name": "ens4",
                  "ip_addr": "10.168.3.137",
                  "network": "10.168.0.0/16"
                },
                {
                  "net_name": "radio_test_paolo",
                  "interface_name": "eth2",
                  "osm_interface_name": "ens5",
                  "ip_addr": "10.170.3.74",
                  "network": "10.170.0.0/16"
                }
              ]
            },
            "vyos_router_flavors": null,
            "snat_rules": [],
            "dnat_rules": []
          }
        ]
      }
    ],
    "blueprint_instance_id": "K2ZSWQ",
    "blueprint_type": "VyOSBlue"
  }
```
