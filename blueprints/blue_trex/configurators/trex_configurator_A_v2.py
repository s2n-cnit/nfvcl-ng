# this file should copy in configurators
from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.util import *


def check_ip(self, ip):
    ip_check = ip.split('.')
    if len(ip_check) != 4:
        logger.error('ValueError: Ip/network address must be in the format of x.x.x.x')
        return False
    for ip in ip_check:
        try:
            if not 0 <= int(ip) <= 255:
                logger.error('Each octet of IP address must be in the range of 0-255')
                return False
        except:
            logger.error('ValueError: Ip address must be in the format of x.x.x.x')
            return False
    return True


def check_mask(self, mask):
    mask_check = mask.split('.')
    if len(mask_check) != 4:
        logger.error('ValueError: Subnet mask must be in the format of x.x.x.x')
        return False
    for items in mask_check:
        try:
            if not 0 <= int(items) <= 255:
                logger.error('Each octet of subnet mask must be in the range of 0-255')
                return False
        except:
            logger.error('ValueError: Subnet mask must be in the format of x.x.x.x')
            return False
    return True


logger = create_logger('Configurator_trex_A')


class Configurator_trex(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args, master_key=None):
        # nsd_id = trex "conf["blueprint_instance_id"]"
        # m_id = 1
        # blue_id = conf["blueprint_instance_id"]
        # args= conf => input post message
        self.type = "trex"
        super(Configurator_trex, self).__init__(nsd_id, m_id, blue_id)
        # this init add some vars also add playbook yaml file!
        logger.info("Configurator_trex_A created")
        logger.info(f"conf output is {args}")
        self.db = persistency.DB()
        # self.role = role

        """"# setting default values
        # I have doubts about default values for trex
        # I dont need these confs for trex !!"""
        # check if the cap2 yaml file name is exist
        if args['config']['cap2_name'] == 'http':
            cap2_name = 'http'

        elif args['config']['cap2_name'] == 'sfr':
            cap2_name = 'sfr'

        elif args['config']['cap2_name'] == 'tcp':
            cap2_name = 'tcp'

        elif 'cap2_name' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['cap2_name'] = 'sfr.yaml'

        if 'run_duration' not in args['config']:
            logger.info('The parameter not defined, the default value of run duration 10s is used')
            args['config']['run_duration'] = '10'

        if 'net1_int_ip' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net1_int_ip'] = '10.0.10.195'
        # Can add to check to be an IP

        # add IP net2
        if 'net2_int_ip' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net2_int_ip'] = '10.0.11.35'

        ansible_vars = [{'run_duration': args['config']['run_duration']},
                        {'cap2_name': args['config']['cap2_name']},
                        {'net1_int_ip': args['config']['net1_int_ip']},
                        {'net2_int_ip': args['config']['net2_int_ip']}
                        ]
        # set the input variable to run the TRex
        # 1- interfaces name. 2- IP. 3- GW. 4- cap2_name. 5- run_duration.
        # acceptable cap2_name: {http, sfr, tcp, sip}
        # add int name
        # exint_index = 4
        # # index3 is reserved for mgmnt
        # # careful about adding dict
        # new version
        # add int name
        exint_index = 4
        ansible_vars[0]['interfaces'] = []
        for nets in args['vims'][0]['extra-nets']:
            ansible_vars[0]['interfaces'].append(f'ens{exint_index}')
            exint_index += 1

        # Add ips as a list
        default_ips = ['10.0.10.195', '10.0.11.35']
        # vars[0]['ips'] = ['']
        ip_list = []
        counter = 0
        for nets in args['vims'][0]['extra-nets']:
            if 'net_int_ips' not in args['config']:
                logger.warning(f"no IP is set for net {counter}=> default value is selected")
                ip_list = default_ips
                logger.info(" default values for two interfaces are selected ")
                break

            elif not check_ip(args['config']['net_int_ips'][counter]):
                # print(f'Not corrected Ip is inserted for net{counter}')
                raise ValueError(f'Wron Ip format is inserted for net{counter}')

            else:
                ip_list.append(args['config']['net_ips'][counter])

        # Add Gateways
        default_gws = ['10.0.10.254', '10.0.11.254']
        gw_list = []
        counter = 0
        for nets in args['vims'][0]['extra-nets']:
            if 'gw_ips' not in args['config']:
                logger.warning(f"no GW is set for net {counter}=> default value is selected")
                gw_list = default_gws
                logger.info(" only two interfaces/gateways are selected ")
                break

            elif not check_ip(args['config']['gw_ips'][counter]):
                # print(f'Not corrected Ip is inserted for net{counter}')
                raise ValueError(f'Not corrected gw is inserted for net{counter}')

            else:
                gw_list.append(args['config']['gw_ips'][counter])

        # check number of interfaces to be even
        # NOTE: think about adding all parameters into one dict and send to ansible (FUTURE Improvement)
        # require to modify also ansible
        # create input dict for ansible and loop over netip and gw==> create "ip_gw" var for ansible
        if len(gw_list) % 2 == 0 and len(ip_list) % 2 == 0:
            if (len(gw_list) % 2) == (len(ip_list) % 2):
                counter = 0
                temp_list = []
                while counter < len(ip_list):
                    temp_list.append({"ip": f"{ip_list[counter]}", "gw": f"{gw_list[counter]}"})
                    counter += 1
                ansible_vars.append({"ip_gw": temp_list})

            else:
                logger.error("For each interface ip a gateway ip is required")
                raise ValueError("For each interface ip a gateway ip is required")
        # check if number of inputs are not correct>>> consider only two first interfaces
        elif len(gw_list) > 2 and len(ip_list) > 2:
            if (len(gw_list) % 2) and (len(ip_list) % 2) != 0:  # check number of interfaces be even
                logger.debug(
                    "TRex works only with even number of extra interfaces only the first two interfaces are applied")
                gw_list_ = gw_list[0:2]  # only the first two items
                ip_list_ = ip_list[0:2]
                counter = 0
                temp_list_ = []
                while counter < len(ip_list_):
                    temp_list.append({"ip": f"{ip_list_[counter]}", "gw": f"{gw_list_[counter]}"})
                    counter += 1
                ansible_vars.append({"ip_gw": temp_list_})

        # create iname_ip_mask (interfaceName, IP, netmask)  input for ansible
        # Think about adding gw also here and remove previous part
        default_masks = ['255.255.255.0', '255.255.255.0']
        # vars[0]['ips'] = ['']
        mask_list = []
        counter = 0
        for nets in args['vims'][0]['extra-nets']:
            if 'net_masks' not in args['config']:
                logger.warning(f"no network_mask is set for net {counter}=> default value is selected")
                mask_list = default_masks
                logger.info(" default values for two interfaces are selected ")
                break

            # check input validation
            elif not check_mask(args['config']['net_masks'][counter]):
                # print(f'Not corrected Ip is inserted for net{counter}')
                raise ValueError(f'Wrong Ip format is inserted for net{counter}')
            else:
                mask_list.append(args['config']['net_masks'][counter])

        if len(mask_list) % 2 == 0 and len(ip_list) % 2 == 0:
            if (len(mask_list) % 2) == (len(ip_list) % 2):
                counter = 0
                temp_list = []
                iname_list = ansible_vars[0]['interfaces']
                while counter < len(ip_list):
                    temp_list.append({"iname": f"{iname_list[counter]}", "ip": f"{ip_list[counter]}", "mask": f"{mask_list[counter]}"})
                    counter += 1
                ansible_vars.append({"iname_ip_mask": temp_list})

            else:
                logger.error("For each interface ip a netmask ip is required")
                raise ValueError("For each interface ip a netmask ip is required")
        # if the number of the inputs are not correct>>> consider only two first interfaces
        elif len(mask_list) > 2 and len(ip_list) > 2:
            if (len(mask_list) % 2) and (len(ip_list) % 2) != 0:  # check number of interfaces be even
                logger.debug(
                    "TRex works only with even number of extra interfaces only the first two interfaces are applied")
                mask_list_ = mask_list[0:2]  # only the first two items
                ip_list_ = ip_list[0:2]
                iname_list_ = ansible_vars[0]['interfaces']
                counter = 0
                temp_list_ = []
                # only the first two are added
                while counter < len(ip_list_):
                    temp_list.append({"iname": f"{iname_list_[counter]}", "ip": f"{ip_list_[counter]}", "gw": f"{mask_list_[counter]}"})
                    counter += 1
                ansible_vars.append({"iname_ip_mask": temp_list_})

        # create client/server start and end ips
        # This is Valid only for two ports===> need to upgrade for more interfaces
        if 'cl_s_ip' not in args['config']:
            logger.warning(f"no client start IP is set => default value is selected")
            mask_list = default_masks
            logger.info(" default values for two interfaces are selected ")
        # for nets in args['vims'][0]['extra-nets']:
        #     if 'net_masks' not in args['config']:
        #         logger.warning(f"no network_mask is set for net {counter}=> default value is selected")
        #         mask_list = default_masks
        #         logger.info(" default values for two interfaces are selected ")
        #         break

            # check input validation
            elif not check_mask(args['config']['net_masks'][counter]):
                # print(f'Not corrected Ip is inserted for net{counter}')
                raise ValueError(f'Wrong Ip format is inserted for net{counter}')
            else:
                mask_list.append(args['config']['net_masks'][counter])



        self.addPlaybook('trex_ansible_install.yaml', vars_=ansible_vars)
        """ 
        open the existed playbook(ansible configuration for running plays to install trex ) with only one task 
        as the name of plays_
        """
        # also added vars (with the name of vars_) to a new part of vars:[] in the play book

    def dump(self):
        logger.info("Dumping")
        self.dumpAnsibleFile(10, 'trex' + str(self.nsd_id) +
                             '_' + str(self.nsd['member-vnfd-id']))
        return super(Configurator_trex, self).dump()

    def get_logpath(self):
        # return [self.conf['log_filename']]
        return []

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs

        # super(Configurator_AmariEPC, self).destroy()
