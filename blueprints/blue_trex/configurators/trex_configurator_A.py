# this file should copy in configurators
from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.log import create_logger

logger = create_logger('Configurator_trex_A')


class Configurator_trex(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args, master_key=None):
        """
        :param nsd_id: trex "conf["blueprint_instance_id"]"
        :param m_id: 1
        :param blue_id: conf["blueprint_instance_id"]
        :param args: conf => input post message
        :param master_key: Not used in this function
        """

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
        # if 'pod_network_cidr' not in args:
        #     args['pod_network_cidr'] = '10.254.0.0/16'
        # if 'load_balancer' not in args:
        #     logger.warn("Load balancer configuration not present.")
        #     args['load_balancer'] = {}
        # if 'mode' not in args['load_balancer']:
        #     args['load_balancer']['mode'] = 'layer2'
        # if args['load_balancer']['mode'] not in ['layer2', 'layer3']:
        #     raise ValueError('Load balancer mode {} not supported'.format(args['load_balancer']['mode']))
        # if 'cni' not in args:
        #     args['cni'] = 'flannel'
        # if args['cni'] not in ['flannel', 'calico']:
        #     raise ValueError('cni plugin {} not supported'.format(args['cni']))
        #
        # jinja_vars = {
        #     'pod_network_cidr': args['pod_network_cidr'],
        #     'lb_ip_start': args['load_balancer']['ip_start'],
        #     'lb_ip_end': args['load_balancer']['ip_end'],
        #     'lb_layer': args['load_balancer']['mode'],
        # }
        #

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
        #     cap2_name = 'sfr'
        #
        # else:
        #     cap2_name = 'sfr'

        if 'run_duration' not in args['config']:
            logger.info('The parameter not defined, the default value of run duration 10s is used')
            args['config']['run_duration'] = '10'
        # else:
        #     run_duration = args['config']['run_duration']
        # try:
        #     if args['config']['cap2_name'] == 'http_simple_mirej.yaml':
        #         cap2_name = 'http_simple_mirej.yaml'
        #
        #     elif args['config']['cap2_name'] == 'sfr.yaml':
        #         cap2_name = 'sfr.yaml'
        #     else:
        #         logger.info("wrong cap name => default value for sfr.yaml is selected")
        #         cap2_name = 'sfr.yaml'
        # except:
        #     raise Warning("not selected cap yaml file in the post message => default value for sfr.yaml is selected")
        #     logger.info("not selected cap yaml file in the post message => default value for sfr.yaml is selected")
        #     cap2_name = 'sfr.yaml'
        # args['config']['cap2_name'] = 'sfr.yaml'

        # check if the time duration is exist
        # try:
        #     run_duration = self.args['config']['run_duration']
        # except:
        #     raise Warning("time duration is not selected => default value is 10s")
        #     logger.info("time duration is not selected => default value is 10s")
        #     run_duration = '10'

        # set the input variable to run the TRex
        # 1- interfaces name. 2- IP. 3- GW. 4- cap2_name. 5- run_duration.
        # acceptable cap2_name: {http, sfr, tcp, sip}

        # ansible_vars = []
        # add IP to ansible vars
        if 'net1_int_ip' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net1_int_ip'] = '10.0.10.195'
        # Can add to check to be an IP

        # add IP net2
        if 'net2_int_ip' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net2_int_ip'] = '10.0.11.35'
        #     net2_int_ip = args['config']['net2_int_ip']
        # else:
        #     net2_int_ip = '10.0.11.35'

        # add gw net1
        if 'net1_gw' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net1_gw'] = '10.0.10.254'
        #     net1_gw = args['config']['net1_gw']
        # else:
        #     net1_gw = '10.0.10.254'

        # add gw net2
        if 'net2_gw' not in args['config']:
            logger.info("wrong cap name => default value for sfr.yaml is selected")
            args['config']['net2_gw'] = '10.0.11.254'
        #     net2_gw = args['config']['net2_gw']
        # else:
        #     net2_gw = '10.0.11.254'
        # ansible_vars = [
        #     {'pod_network_cidr': args['pod_network_cidr']},
        #     {'trex_ip': args['config']['trex_ip']},
        #     # {'pod_network_manifest_file': args['pod_network_manifest_file']},
        #     {'metallb_configmap_file': "~/metallb_config.yaml"},
        #     {'cni': args['cni']}
        # ]
        # if 'linkerd' in args:
        #      ansible_vars.append({'linkerd': args['linkerd']})
        ansible_vars = [{'run_duration': args['config']['run_duration']},
                        {'cap2_name': args['config']['cap2_name']},
                        {'net1_int_ip': args['config']['net1_int_ip']},
                        {'net2_int_ip': args['config']['net2_int_ip']},
                        {'net1_gw': args['config']['net1_gw']},
                        {'net2_gw': args['config']['net2_gw']}
                        ]

        # add int name
        exint_index = 4
        # index3 is reserved for mgmnt
        # careful about adding dict
        for nets in args['vims'][0]['extra-nets']:
            ansible_vars.append({f"int{exint_index}": f'ens{exint_index}'})
            exint_index += 1

        self.addPlaybook('trex_ansible_install.yaml', vars_=ansible_vars)
        """ 
        open the existed playbook(ansible configuration for running plays to install trex ) with only one task 
        as the name of plays_
        """
        # also added vars (with the name of vars_) to a new part of vars:[] in the play book

        """
        Dont need this part too I would use only ansible yaml file
        """
        # if self.role is 'master':
        #     if args['cni'] is 'flannel':
        #         self.addJinjaTemplateFile(
        #             {'template': 'config_templates/k8s_kube_flannel.yaml',
        #              'path': '~/',
        #              'transfer_name': "flannel_config_{}.yaml".format(blue_id),
        #              'name': "kube_cni.yaml"
        #              }, jinja_vars)
        #     if args['cni'] is 'calico':
        #         self.addJinjaTemplateFile(
        #             {'template': 'config_templates/k8s_calico.yaml',
        #              'path': '~/',
        #              'transfer_name': "calico_config_{}.yaml".format(blue_id),
        #              'name': "kube_cni.yaml"
        #              }, jinja_vars)
        #         self.addJinjaTemplateFile(
        #             {'template': 'config_templates/k8s_calico_custom.yaml',
        #              'path': '~/',
        #              'transfer_name': "calico_config_{}.yaml".format(blue_id),
        #              'name': "kube_calico_custom.yaml"
        #              }, jinja_vars)
        #
        #     self.addJinjaTemplateFile(
        #         {'template': 'config_templates/k8s_metallb_manifest.yaml',
        #          'path': '~/',
        #          'transfer_name': "metallb_manifest_{}.yaml".format(blue_id),
        #          'name': "metallb_manifest.yaml"
        #          }, jinja_vars)
        #     self.addJinjaTemplateFile(
        #         {'template': 'config_templates/metallb_config.yaml',
        #          'path': '~/',
        #          'transfer_name': "metallb_config_{}.yaml".format(blue_id),
        #          'name': "metallb_config.yaml"
        #          }, jinja_vars)
        #     self.addJinjaTemplateFile(
        #         {'template': 'config_templates/k8s_openebs_operator.yaml',
        #          'path': '~/',
        #          'transfer_name': "openebs_operator_{}.yaml".format(blue_id),
        #          'name': "openebs_operator.yaml"
        #          }, jinja_vars)
        #     self.addJinjaTemplateFile(
        #         {'template': 'config_templates/k8s_default_storageclass.yaml',
        #          'path': '~/',
        #          'transfer_name': "default_storageclass_{}.yaml".format(blue_id),
        #          'name': "default_storageclass.yaml"
        #          }, jinja_vars)
        #     self.addJinjaTemplateFile({
        #         'template': 'config_templates/k8s_regcred.yaml',
        #         'path': '~/',
        #         'transfer_name': "regcred_{}.yaml".format(blue_id),
        #         'name': "regcred.yaml"
        #     }, jinja_vars)
        #     self.appendPbTasks('config_templates/playbook_kubernetes_master.yaml')
        #
        # if self.role is 'worker':
        #     self.appendPbTasks('config_templates/playbook_kubernetes_worker.yaml')

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

