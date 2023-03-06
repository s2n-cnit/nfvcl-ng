import itertools

from blueprints.blueprint import BlueprintBase
from configurators.vyos_configurator import Configurator_MultiVyOs
from utils import persistency
import json

db = persistency.DB()


class VyOsMultipleTunnels(BlueprintBase):
    def __init__(self, conf, id_, recover):
        self.vnfd = [{'id': 'router_vnfd', 'name': 'vyos-vnf_vnfd'}]
        BlueprintBase.__init__(self, conf, id_)
        self.nsd()

    def getBlueprintParams(self):
        return {'slice_id': self.conf['slice'], 'type': 'tunnel'}

    def nsd(self):
        # check the links among routers, if they are not listed build a full-mesh
        ids_ = []
        print(json.dumps(self.conf))
        for v in self.conf['config']['vims']:
            ids_.append(v['id'])

        if len(self.conf['config']['links']) == 0:
            # in this case we need to build a full mesh
            comb = list(itertools.combinations(ids_, 2))
            for l in comb:
                self.conf['config']['links'].append({'from': l[0], 'to': l[1]})

        # create the array of nsds, one for each router
        #serv_count = 1
        for serv in self.conf['config']['vims']:
            serv['nsd_index'] = serv['id']

            n_ = self.findNsdTemplate('service', 'tunnel', {
                                      'include': [], 'exclude': []})
            n_['name'] = 'vyost-' + \
                str(self.conf['slice']) + '_' + str(serv['id']) + '_nsd'
            n_['short-name'] = 'vyost-' + \
                str(self.conf['slice']) + '_' + str(serv['id']) + '_nsd'
            n_['id'] = 'tunnel_' + \
                str(self.conf['slice']) + '_' + str(serv['id'])
            n_ = self.updateVnfdNames(self.vnfd, n_)

            for link in n_['vld']:
                if link['id'] == 'wan_vld':
                    link['vim-network-name'] = serv['wan']['id']
                if link['id'] == 'mgt_vld':
                    link['vim-network-name'] = serv['mgt']
                if link['id'] == 'lan_vld':
                    link['vim-network-name'] = serv['lan']
                    link['name'] = serv['name'] + ' lan'

            #print(yaml.dump(n_, allow_unicode=True, default_flow_style=False))
            self.nsd_.append({
                'status': 'born',
                'vim': serv['name'],
                'descr': {'nsd:nsd-catalog': {'nsd': [n_]}}
            })

    def get_ip(self, nbiUtil):
        for n in self.nsd_:
            ip_address = nbiUtil.get_ip_address(
                n['nsi_id'], "wan_vld")[0]['ip']+'/24'
            vim_id = n['descr']['nsd:nsd-catalog']['nsd'][0]['name'].split('_')[
                1]
            #print('vim '+ vim_id + ' ----> wan ip: ' + ip_address)
            for v in self.conf['config']['vims']:
                if v['id'] == vim_id:
                    v['wan']['ip'] = ip_address
                    break

    def init_day2_conf(self):
        res = []
        # allocate a configurator for each VyOS VNF
        self.vnf_configurator = []

        for v_ in self.conf['config']['vims']:
            # identifying the remote peers
            peers = []
            net_id = 1
            for l_ in self.conf['config']['links']:
                if l_['from'] == v_['id']:
                    peers.append({
                        'id': l_['to'],
                        'remote_ip': str(next(item for item in self.conf['config']['vims'] if item['id'] == l_['to'])['wan']['ip']),
                        'net_id': net_id
                    })
                if l_['to'] == v_['id']:
                    peers.append({
                        'id': l_['from'],
                        'remote_ip': str(next(item for item in self.conf['config']['vims'] if item['id'] == l_['from'])['wan']['ip']),
                        'net_id': net_id
                    })
                net_id += 1
            print(peers)
            self.vnf_configurator.append(Configurator_MultiVyOs(
                'vyost-' + str(self.conf['slice']) + '_' + str(v_['id']) + '_nsd', 1, int(v_['id']), v_['wan']['ip'], peers))
            res += self.vnf_configurator[-1].dump()
        self.save_conf()
        return res

    def destroy(self):
        #if hasattr(self, 'wan_ipd'):
        #for v_ in self.conf['config']['vims']:
        #    wan_ipd.release(v_['wan']['ip'])
        self.del_conf()
