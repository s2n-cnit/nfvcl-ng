from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.util import *
# from ruamel.yaml import YAML

logger = create_logger('Configurator_Amari5GC')


class Configurator_Amari5GC(Configurator_Flex):
    def __init__(self, nsd_id: str, m_id: int, blue_id: str, args: dict, interfaces=None):
        self.type = "amari5gc"
        super(Configurator_Amari5GC, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Configurator_Amari5GC allocated")
        self.day2_conf_file_name = 'amari_5GC_plmn_' + str(args['plmn']) + "_blue_" + blue_id + '.conf'
        self.ue_db_filename = 'ue_db_nfvcl.cfg'
        self.db = persistency.DB()

        self.conf = {'plmn': args['plmn'], 'gtp_ip': None}

        if 'pdn_list' in args:
            self.conf['pdn'] = args['pdn_list']
        else:
            self.default_pdn()

        if 'tunnels' in args:
            if args['tunnels']:
                # in case of tunnels we should use IP addresses of the overlay net
                self.conf['gtp_ip'] = args['config']['epc_s1_ip']
        if self.conf['gtp_ip'] is None:
            for intf in interfaces:
                if intf['vld'] == 'data':
                    self.conf['gtp_ip'] = intf['ip']
                    break

        if 'tunnels' in args:  # placeholder for future work
            # create the bridge
            self.addShellCmds(
                    {'template': 'config_templates/add_br.shell'},
                    [
                       {'placeholder': '__OVERLAYIP__', 'value': args['config']['epc_s1_ip']},
                       {'placeholder': '__OVERLAYIPMASK__', 'value': '24'},
                       {'placeholder': '__BRIDGE_NAME__', 'value': 'br_s1'}
                    ]
            )
            # create the vxlan and add it to the bridge
            for t in args['tunnels']:
                vxlan_dict = [
                    {'placeholder': '__VNI__', 'value': str(t['vni'])},
                    {'placeholder': '__REMOTEIP__', 'value': t['remote_ip'].split('/')[0]},
                    {'placeholder': '__LOCALIP__', 'value': t['local_ip'].split('/')[0]},
                    {'placeholder': '__BRIDGE_NAME__', 'value': 'br_s1'}
                ]
                self.addShellCmds({'template': 'config_templates/vxlan_bridge.shell'}, vxlan_dict)

        # create 5GC conf file and restart services
        self.build_5GC_conf()

    def build_5GC_conf(self) -> None:
        self.conf_data = {
            'plmn': self.conf['plmn'],
            'gtp_addr': self.conf['gtp_ip'].split('/')[0],
            'license_server': "192.168.11.2",
            'mme_code': 1,
            'network_name': "CNIT S2N Network",
            'network_short_name': "CNIT S2N",
            'pdn': self.conf['pdn'],
            'ue_db_file': self.ue_db_filename
        }
        self.addJinjaTemplateFile(
            {'template': 'config_templates/amari5GC.jinja2',
             'path': '/root/mme/config/',
             'transfer_name': self.day2_conf_file_name,
             'name': 'mme_nfvcl.cfg'
             }, self.conf_data)

        # create UE db file
        ue = self.db.findone_DB('ue', {"plmn": str(self.conf['plmn'])})
        self.addJinjaTemplateFile(
            {'template': 'config_templates/amari_ue.jinja2',
             'path': '/root/mme/config/',
             'transfer_name': 'ue_db_plmn_' + str(self.conf['plmn']) + 'cfg',
             'name': self.ue_db_filename
             }, {'ue_list': ue['ue_db']})

        self.addTemplateFile(
            {'template': 'config_templates/mme-ifup',
             'path': '/root/mme/config/',
             'transfer_name': 'amari_mme_ifup',
             'name': 'mme-ifup'
             }, [])

        # reload Amarisoft services
        self.addShellCmds({'template': 'config_templates/amari_epc_init.shell'}, {})

    def add_pdn(self, data: dict) -> list:
        logger.info("adding DNN " + data['name'])
        check_pdn = next((item for item in self.conf['pdn'] if item['name'] == data['name']), None)
        if check_pdn is not None:
            raise ValueError('pdn ' + data['name'] + ' already existing! Aborting action.')
        self.conf['pdn'].append(data)
        return self.build_5GC_conf()

    def del_pdn(self, apn_name: str) -> list:
        logger.error("deleting APN not implemented")
        check_pdn = next((item for item in self.conf['pdn'] if item['name'] == apn_name), None)
        if check_pdn is None:
            raise ValueError('pdn ' + apn_name + ' not existing! Aborting action.')
        new_pdns = [item for item in self.conf['pdn'] if item['name'] is not apn_name]
        self.conf['pdn'] = new_pdns
        return self.build_5GC_conf()

    def add_slice(self, data: dict) -> list:
        pdn_item = next((item for item in self.conf['pdn'] if item['name'] == data['plmn']), None)
        if pdn_item is None:
            raise ValueError('pdn ' + data['plmn'] + ' not existing! Aborting action.')
        if 'nssai' not in self.conf_data:
            self.conf_data['nssai'] = []
        nssai_item = {'sst': data['sst']}
        snssai_item = {
            'sst': data['sst'],
            'qos_flows': []
        }
        if 'sd' in data:
            nssai_item['sd'] = data['sd']
            snssai_item['sd'] = data['sd']

        self.conf_data['nssai'].append(nssai_item)
        for f in data['qos_flows']:
            snssai_item['qos_flows'].append(f)
        pdn_item['slices'].append(snssai_item)
        return self.build_5GC_conf()

    def del_slice(self, data: dict) -> list:
        pdn_item = next((item for item in self.conf['pdn'] if item['name'] == data['plmn']), None)
        if pdn_item is None:
            raise ValueError('pdn ' + data['plmn'] + ' not existing! Aborting action.')

        nssai_index = next((index for index, item in enumerate(self.conf_data['nssai']) if item['sst'] == data['sst']), None)
        self.conf_data['nssai'].pop(nssai_index)
        snssai_index = next((index for index, item in enumerate(pdn_item['slices']) if item['sst'] == data['sst']), None)
        pdn_item['slices'].pop(snssai_index)
        return self.build_5GC_conf()

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'ansible_amari5gc_'+str(self.nsd_id) +
                             '_'+str(self.nsd['member-vnfd-id']) + '_' + self.blue_id)
        return super(Configurator_Amari5GC, self).dump()

    def get_logpath(self):
        return [self.conf['log_filename']]

    def acquire_license(self):
        logger.info("Acquire license")
        license_servers = self.db.find_DB("license", {"license.type": "amariepc", "license.version": "2019-02-05"})
        license_ip = ""
        for server in license_servers:
            if server["license"]["number"] > len(server["license"]["consumer"]):
                license_ip = server["license"]["ip"]
                server["license"]["consumer"].append(self.conf['plmn'])
                #.update_one(filter, {"$set": data})
                res = self.db.update_DB("license", server, {'license.ip': server['license']['ip'], 'license.type': server['license']['type']})
                print(res)
                break

        if license_ip is "":
            raise ValueError("no Amarisoft License Servers available")

        return license_ip

    def release_license(self):
        logger.info("Release license")
        license_servers = self.db.find_DB("license",{"license.type": "amariepc", "license.ip": self.conf["license_server"]["server_addr"]})
        for server in license_servers:
            if self.conf['plmn'] in server["license"]["consumer"]:
                server["license"]["consumer"].remove(self.conf['plmn'])
                self.db.update_DB("license", server, {'license.ip': server['license']['ip'], 'license.type': server['license']['type']})
                break

    def custom_prometheus_exporter(self):
        # transfer and run as daemon the amari exporter
        self.addPackage('screen')
        self.addPackage('python3-prometheus-client')
        self.addPackage('python3-websocket')
        self.addTemplateFile(
            {'template': 'vnf_binpackages/amari_exporter.py',
             'path': '/root/',
             'transfer_name': 'amari_exporter.py',
             'name': 'amari_exporter.py'
            }, {})
        placeholder_dict = [
                    {'placeholder': '__WEBSOCKET_IP__', 'value': 'localhost'},
                    {'placeholder': '__WEBSOCKET_PORT__', 'value': '9000'},
                    {'placeholder': '__TYPE__', 'value': 'mme'},
                    {'placeholder': '__PLMN__', 'value': str(self.conf['plmn']) },
                    {'placeholder': '__EXPORTER_PORT__', 'value': '9999' },
                    {'placeholder': '__POLLING_TIME__', 'value': str(10) },
                ]
        self.addTemplateFile(
            {'template': 'config_templates/amari_exporter.yaml',
             'path': '/root/',
             'transfer_name': 'amari_exporter.yaml',
             'name': 'config.yaml'
            }, placeholder_dict)
        self.addShellCmds(
            {'template': 'config_templates/amari_exporter.shell'}, {})
        return [str(self.mng_ip)+':9999']

    def default_pdn(self) -> None:
        self.conf['pdn'] = [
            {
                'type': 'ipv4',
                'name': 'default',
                'first_ip4': '10.150.1.2',
                'last_ip4': '10.150.1.250',
                'shift_ip4': 2,
                'dns_list': '8.8.8.8',
                'erabs': [{'qci': 9, 'prio': 15}]
            },
            {
                'type': 'ipv4',
                'name': 'internet',
                'first_ip4': '10.150.2.2',
                'last_ip4': '10.150.2.250',
                'shift_ip4': 2,
                'dns_list': '8.8.8.8',
                'erabs': [{'qci': 9, 'prio': 15}]
            },
            {
                'type': 'ipv4',
                'name': 'sos',
                'first_ip4': '10.150.3.2',
                'last_ip4': '10.150.3.250',
                'shift_ip4': 2,
                'dns_list': '8.8.8.8',
                'erabs': [{'qci': 5, 'prio': 15}]
            },
            {
                'type': 'ipv4',
                'name': 'ims',
                'first_ip4': '10.150.4.2',
                'last_ip4': '10.150.4.250',
                'shift_ip4': 2,
                'dns_list': '8.8.8.8',
                'p_cscf_addr': '10.150.4.1',
                'erabs': [{'qci': 5, 'prio': 15}]
            },
        ]

    def destroy(self):
        logger.info("Destroying")
        self.release_license()
        #TODO remove prometheus jobs

        #super(Configurator_AmariEPC, self).destroy()


