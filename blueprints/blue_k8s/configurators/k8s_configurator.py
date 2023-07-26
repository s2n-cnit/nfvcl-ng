from configurators.flex_configurator import Configurator_Flex
from utils import persistency
from utils.log import create_logger

logger = create_logger('Configurator_K8s')


class ConfiguratorK8s(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id, args, role='worker', master_key=None):
        self.type = "k8s"
        super(ConfiguratorK8s, self).__init__(nsd_id, m_id, blue_id)
        logger.info("Blue {}: Configurator_K8s created for nsd {} and vnfd {}".format(blue_id, nsd_id, m_id))
        self.db = persistency.DB()

        if role not in ['worker', 'master']:
            raise ValueError('Configurator_K8s role {} not supported'.format(role))

        self.role = role

        jinja_vars = {
            'pod_network_cidr': args['config']['pod_network_cidr'],
            'lb_pools': args['config']['network_endpoints']['data_nets']
        }
        logger.debug(jinja_vars)
        ansible_vars = []
        if self.role == 'master':
            ansible_vars = [
                {'pod_network_cidr': args['config']['pod_network_cidr']},
                # ^-- repeated here because it is used as ansible vars in playbook_kubernetes_master.yml
                # {'rbac_manifest_file': args['rbac_manifest_file']},
                {'k8s_master_ip': args['config']['controller_ip']},
                # {'pod_network_manifest_file': args['pod_network_manifest_file']},
                {'metallb_configmap_file': "~/metallb_config.yaml"},
                {'cni': args['config']['cni']}
                # Default cni is flannel -> See K8sConfig model
            ]
            if 'linkerd' in args:
                ansible_vars.append({'linkerd': args['linkerd']})

        if self.role == 'worker':
            ansible_vars = [{'master_key': master_key}]

        self.addPlaybook('blueprints/blue_k8s/config_scripts/playbook_kubernetes_common.yaml', vars_=ansible_vars)

        if self.role == 'master':
            self.appendPbTasks('blueprints/blue_k8s/config_scripts/playbook_kubernetes_master.yaml')

        if self.role == 'worker':
            self.appendPbTasks('blueprints/blue_k8s/config_scripts/playbook_kubernetes_worker.yaml')

    def add_worker_label(self, workers_to_label):
        self.resetPlaybook()
        logger.info("Adding the worker labels")
        for item in workers_to_label:
            area_id = item['area']
            vm: str
            for vm in item['vm_names']:
                task_name = 'Add label to worker {}'.format(vm)
                vm = vm.replace('_', '-')
                vm = vm.lower()
                task_command = 'kubectl label nodes {} area={}'.format(vm, area_id)
                self.playbook['tasks'].append({'name': task_name, 'command': task_command})

    def dump(self):
        logger.debug("Blue {}: Dumping nsd {}".format(self.blue_id, self.nsd_id))
        self.dumpAnsibleFile(10, str(self.nsd_id) + '_ansible_k8s_' + str(self.nsd['member-vnfd-id']))
        return super(ConfiguratorK8s, self).dump()

    def get_logpath(self):
        # return [self.conf['log_filename']]
        return []

    def custom_prometheus_exporter(self):
        # self.addPackage('screen')
        pass

    def destroy(self):
        logger.info("Destroying")
