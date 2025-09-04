from utils import get_unittest_config

unittest_config = get_unittest_config()

TOPOLOGY_OK = {
    "id": "topology",
    "vims": [
        {
            "name": "OSLAB",
            "vim_type": "openstack",
            "schema_version": "1.0",
            "vim_url": unittest_config.config.vim.url,
            "vim_tenant_name": unittest_config.config.vim.tenant, # TODO refactor after vim change
            "vim_user": unittest_config.config.vim.user,
            "vim_password": unittest_config.config.vim.password,
            "config": {
                "insecure": True,
                "APIversion": "v3.3",
                "use_floating_ip": False
            },
            "networks": [
                unittest_config.config.networks.mgmt.name,
                unittest_config.config.networks.data.name,
                unittest_config.config.networks.n3.name,
                unittest_config.config.networks.n6.name,
                unittest_config.config.networks.gnb.name
            ],
            "routers": [],
            "areas": [
                1,
                2,
                3,
                4
            ]
        }
    ],
    "kubernetes": [],
    "networks": [
        {
            "name": unittest_config.config.networks.mgmt.name,
            "external": False,
            "type": "vxlan",
            "vid": None,
            "dhcp": True,
            "ids": [],
            "cidr": unittest_config.config.networks.mgmt.cidr,
            "gateway_ip": unittest_config.config.networks.mgmt.gateway,
            "allocation_pool": [],
            "reserved_ranges": [],
            "dns_nameservers": []
        },
        {
            "name": unittest_config.config.networks.data.name,
            "external": False,
            "type": "vxlan",
            "vid": None,
            "dhcp": True,
            "ids": [],
            "cidr": unittest_config.config.networks.data.cidr,
            "gateway_ip": None,
            "allocation_pool": [],
            "reserved_ranges": [],
            "dns_nameservers": []
        },
        {
            "name": unittest_config.config.networks.n3.name,
            "external": False,
            "type": "vxlan",
            "vid": None,
            "dhcp": True,
            "ids": [],
            "cidr": unittest_config.config.networks.n3.cidr,
            "gateway_ip": None,
            "allocation_pool": [],
            "reserved_ranges": [],
            "dns_nameservers": []
        },
        {
            "name": unittest_config.config.networks.n6.name,
            "external": False,
            "type": "vxlan",
            "vid": None,
            "dhcp": True,
            "ids": [],
            "cidr": unittest_config.config.networks.n6.cidr,
            "gateway_ip": None,
            "allocation_pool": [],
            "reserved_ranges": [],
            "dns_nameservers": []
        },
        {
            "name": unittest_config.config.networks.gnb.name,
            "external": False,
            "type": "vxlan",
            "vid": None,
            "dhcp": True,
            "ids": [],
            "cidr": unittest_config.config.networks.gnb.cidr,
            "gateway_ip": None,
            "allocation_pool": [],
            "reserved_ranges": [],
            "dns_nameservers": []
        }
    ],
    "routers": [],
    "pdus": [],
    "prometheus_srv": []
}

VIM_TO_ADD1 = {
    "name": "OSLAB1",
    "vim_type": "openstack",
    "schema_version": "1.0",
    "vim_url": "http://os-lab2.maas:5000/v3",
    "vim_tenant_name": "user", # TODO refactor after vim change
    "vim_user": "user",
    "vim_password": "pwd",
    "config": {
        "insecure": True,
        "APIversion": "v3.3",
        "use_floating_ip": False
    },
    "networks": [
        "dmz-internal",
        "test-net"
    ],
    "routers": [],
    "areas": [
        0,
        1,
        2,
        3,
        4
    ]
}

VIM_TO_ADD2 = {
    "name": "OSLAB2",
    "vim_type": "openstack",
    "schema_version": "1.0",
    "vim_url": "http://os-lab2.maas:5000/v3",
    "vim_tenant_name": "user", # TODO refactor after vim change
    "vim_user": "user",
    "vim_password": "pwd",
    "config": {
        "insecure": True,
        "APIversion": "v3.3",
        "use_floating_ip": False
    },
    "networks": [
        "dmz-internal",
        "test-net"
    ],
    "routers": [],
    "areas": [
        5
    ]
}

PDU_TO_ADD = {
    "name": "Amarisoft",
    "area": 3,
    "type": "GNB",
    "instance_type": "AmarisoftGNB",
    "network_interfaces": [
        {
            "name": "Mgmt",
            "mgmt": True,
            "ip": "192.168.10.2"
        }
    ],
    "username": "root",
    "password": "root",
    "config": {
        "nr_tdd": 1,
        "nr_tdd_config": 2,
        "nr_bandwidth": 40,
        "n_antenna_dl": 1,
        "n_antenna_ul": 1,
        "use_srs": 0,
        "logfile": "/tmp/gnb0.log"
    }
}

K8S_TO_ADD = {
    "name": "testcluster",
    "provided_by": "NFVCL",
    "blueprint_ref": "",
    "deployed_blueprints": [],
    "credentials": "string",
    "vim_name": "string",
    "k8s_version": "v1.24",
    "networks": [
        {
            "name": "dmz-internal",
            "interface_name": "ens3",
            "multus_enabled": False,
            "ip_pools": []
        },
    ],
    "areas": [
        0
    ],
    "cni": "string",
    "cadvisor_node_port": 0,
    "nfvo_status": "not_onboarded",
    "nfvo_onboard": True,
    "anti_spoofing_enabled": True
}

PROMETHEUS_TO_ADD = {
    "id": "proname",
    "ip": "127.0.0.1",
    "port": "9100",
    "user": "ubuntu",
    "password": "ubuntu",
    "ssh_port": 22,
    "targets": [
        {
            "targets": ["192.168.1.2"],
            "labels": {"examplelabel": "test"}
        }
    ],
    "sd_file_location": "sd_targets.yml"
}
