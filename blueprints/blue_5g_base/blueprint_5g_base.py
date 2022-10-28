import importlib
from typing import List, Optional
from abc import ABC, abstractmethod
from blueprints.blueprint import BlueprintBase
from nfvo.nsd_manager import sol006_NSD_builder
from utils.util import create_logger

# create logger
logger = create_logger('Abstract5GBlue')


class Blue5GBase(BlueprintBase, ABC):

    @abstractmethod
    def setVnfd(self, area: str, tac: int = 0, vls: list = None, pdu: dict = None) -> None:
        pass

    @abstractmethod
    def getVnfd(self, area: str, tac: Optional[str] = None) -> list:
        pass

    @abstractmethod
    def core_nsd(self) -> List[str]:
        pass

    @abstractmethod
    def edge_nsd(self, area: dict, vim_name: str) -> List[str]:
        pass

    def ran_nsd(self, area: dict, vim_name: str) -> str:  # differentianting e/gNodeB?
        # NOTE: no bypass here!
        logger.info("Blue {} - Creating RAN NSD(s) for area {} on vim {}".format(self.get_id(), area['id'], vim_name))
        pdu = self.topology_get_pdu_by_area_and_type(area['id'], 'nb')

        if pdu is None:
            raise ValueError('pdu not found for tac ' + str(area['id']))
        logger.info("Blue {} - for area {} pdu {} ({}) selected"
                    .format(self.get_id(), area['id'], pdu['name'], pdu['implementation']))
        self.setVnfd('tac', area['id'], pdu=pdu)

        param = {
            'name': '{}_NGRAN_{}'.format(self.get_id(), area['id']),
            'id': '{}_NGRAN_{}'.format(self.get_id(), area['id']),
            'type': 'ran'
        }
        vim_net_mapping = [
            {'vld': 'mgt', 'vim_net': self.conf['config']['network_endpoints']['mgt'], "mgt": True},
            {'vld': 'data', 'vim_net': self.conf['config']['network_endpoints']['wan'], "mgt": False}
        ]
        n_obj = sol006_NSD_builder(self.getVnfd('tac', area['id']), vim_name, param, vim_net_mapping)
        nsd_item = n_obj.get_nsd()
        nsd_item['area'] = area['id']
        nsd_item['vld'] = pdu['interface']
        self.nsd_.append(nsd_item)
        return param['name']

    def nsd(self) -> List[str]:
        nsd_names = self.core_nsd()
        for area in self.conf['areas']:
            vim = self.get_vim_name(area['id'])
            nsd_names.append(self.ran_nsd(area, vim))
            nsd_names.extend(self.edge_nsd(area, vim))
        logger.info("Blue {} - created NSDs: {}".format(self.get_id(), nsd_names))
        return nsd_names

    def del_area(self, msg: dict) -> List[str]:
        nsi_to_delete = []
        for area in msg['areas']:
            # check if tac is present in conf and if we have a nsi
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if not checked_area:
                raise ValueError("Blue {} - area {} not found".format(self.get_id(), area['id']))

            logger.debug("Blue {} - deleting RAN and edge services on area {}".format(self.get_id(), area['id']))
            # find nsi to be deleted
            for n in self.nsd_:
                if n['area'] == area['id'] and (n['type'] == 'edge' or n['type'] == 'ran'):  # Fixme: add type to nsd
                    logger.debug("Worker on area {} has nsi_id: {}".format(area['id'], n['nsi_id']))
                    nsi_to_delete.append(n['nsi_id'])
            # removing items from conf
            # Note: this should be probably done, after deletion confirmation from the nfvo
            self.conf['areas'] = [item for item in self.conf['areas'] if item['id'] != area['id']]
        return nsi_to_delete

    def add_area(self, msg: dict) -> List[str]:
        logger.info("Blue {} - Adding areas to 5G network blueprint".format(self.get_id()))
        nsd_names = []
        for area in msg['add_areas']:
            logger.info("Blue {} - activating new area {}".format(self.get_id(), area['id']))
            # check if area is already existing in self.conf, or it is a new area
            checked_area = next((item for item in self.conf['areas'] if item['id'] == area['id']), None)
            if checked_area:
                raise ValueError("Blue {} - area {} already exists!".format(self.get_id(), area['id']))

            nsd_names.append(self.ran_nsd(area, self.get_vim_name(area['id'])))
            nsd_names.append(self.edge_nsd(area, self.get_vim_name(area['id'])))
            self.conf['areas'].append(area)
        return nsd_names

    def ran_day2_conf(self, arg: dict, nsd_item: dict) -> list:
        logger.info("Blue {} - Initializing RAN Day2 configurations".format(self.get_id()))
        # here we have to find the correct enb_configurator
        res = []

        # retrieving vim and tac nodes from self.conf
        area = next(item for item in self.conf['areas'] if item['id'] == nsd_item['area'])
        vim = self.get_vim_name(nsd_item['area'])
        pdu_item = self.topology_get_pdu_by_area_and_type(area['id'], 'nb')
        # pdu_item = db.findone_DB('pdu', {'tac': str( tac['id'] )})

        # TODO: here we should probably check which kind of RAN we are going to realize (4G, 5G NSA, 5G SA, ...)
        # TODO: support tunnels

        # allocating the correct configurator obj for the pnf
        nb_configurator = self.db.findone_DB('pnf', {'type': pdu_item['implementation']})
        module = importlib.import_module(nb_configurator['module'])
        Configurator_NB = getattr(module, nb_configurator['name'])

        if len(nsd_item['vld']) > 1:
            wan_vld = next((item for item in nsd_item['vld'] if item['vld'] == 'data'), None)
            if wan_vld is None:
                raise ValueError('wan  vld not found')
        else:
            # this is for pnf with only 1 interface
            wan_vld = nsd_item['vld'][0]

        conf_data = {
           'plmn': str(self.conf['plmn']),
           'tac': nsd_item['area'],
           'gtp_ip': area['nb_wan_ip'],
           # 'mme_ip': self.conf['config']['core_wan_ip'],
           'wan_nic_name': wan_vld['name'],
        }
        if 'core_wan_ip' in self.conf['config']:  # the mme/amf IP for Amari-based cores
            conf_data['mme_ip'] = self.conf['config']['core_wan_ip']
        if 'mme_ip' in self.conf['config']:  # the mme IP for open5GS-based cores
            conf_data['mme_ip'] = self.conf['config']['mme_ip']
        if 'amf_ip' in self.conf['config']:  # the amf IP for open5GS-based cores
            conf_data['amf_ip'] = self.conf['config']['amf_ip']

        # add already enabled slices to the ran
        if 'nssai' in self.conf:  #Fixme update to the new intent schema
            conf_data['nssai'] = self.conf['nssai']
        # override gnb settings from arg
        if 'nb_config' in self.conf:
            conf_data['nb_config'] = self.conf['nb_config']
        if 'tunnel' in self.conf:
            conf_data['tunnel'] = self.conf['tunnel']

        conf_obj = Configurator_NB(
            '{}_NGRAN_{}'.format(self.get_id(), nsd_item['area']),
            1,
            self.get_id(),
            conf_data
        )
        self.vnf_configurator.append(conf_obj)
        res += conf_obj.dump()
        logger.info("e/gNB configuration built for tac " + str( nsd_item['tac'] ))
        return res

    @abstractmethod
    def edge_day2_conf(self, arg: dict, nsd_item: dict) -> List[str]:
        pass

    @abstractmethod
    def init_day2_conf(self, msg: dict) -> list:
        pass

    @abstractmethod
    def get_ip(self) -> None:
        pass

    @abstractmethod
    def _destroy(self):
        pass

    """def add_tac_conf(self, msg: dict) -> list:
        res = []
        for msg_vim in msg['vims']:
            if 'tacs' in msg_vim:
                for msg_tac in msg_vim['tacs']:
                    nsd = None
                    for nsd_item in self.nsd_:
                        if nsd_item['type'] == 'ran':
                            if nsd_item['tac'] == msg_tac['id']:
                                nsd = nsd_item
                                break
                    if nsd is None:
                        raise ValueError('nsd for tac {} not found'.format(msg_tac['id']))
                    res += self.ran_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
                    edge_res = self.edge_day2_conf({'vim': msg_vim['name'], 'tac': msg_tac['id']}, nsd)
                    if edge_res :
                        res += edge_res
        return res

    def del_tac_conf(self, msg: dict) -> list:
        pass"""



    """def add_slice_conf(self, msg: dict) -> list:
        # msg = {conf: {'plmn'=, 'sst'=, 'sd'=, 'qos_flows'=, 'tacs'=[]}}
        logger.info("Adding 5G slice(s)")
        res = []
        for configurator in self.vnf_configurator:
            # the operations are evaluated within the configurator
            # (e.g., the nb does add anything if there is not its tac)
            res += configurator.add_slice(msg['conf'])
        return res

    def del_slice_conf(self, msg: dict) -> list:
        # msg = {conf: {'plmn'=, 'sst'=, 'sd'=, 'qos_flows'=, 'tacs'=[]}}
        logger.info("Deleting 5G slice(s)")
        res = []
        for configurator in self.vnf_configurator:
            # the operations are evaluated within the configurator
            # (e.g., the nb does add anything if there is not its tac)
            res += configurator.add_slice(msg['conf'])
        return res"""

