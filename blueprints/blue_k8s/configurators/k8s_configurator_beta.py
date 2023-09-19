from logging import Logger
from configurators.flex_configurator import Configurator_Flex
from models.k8s.blueprint_k8s_model import K8sBlueprintModel
from utils import persistency
from utils.log import create_logger

logger: Logger = create_logger('K8S CONF')


class ConfiguratorK8sBeta(Configurator_Flex):
    def __init__(self, nsd_id, m_id, blue_id: str, config_model: K8sBlueprintModel, role='worker', master_key=None,
                 step: int = 1):
        self.type = "k8s"
        super(ConfiguratorK8sBeta, self).__init__(nsd_id, m_id, blue_id)
        # Must set after initialization of father, otherwise self.dump_number is reset to 1!!!
        self.dump_number = step
        logger.info("Blue {}: Configurator_K8s created for nsd {} and vnfd {}".format(blue_id, nsd_id, m_id))
        self.db = persistency.DB()

        if role not in ['worker', 'master']:
            raise ValueError('Configurator_K8s role {} not supported'.format(role))

        self.role = role

        ansible_vars = []

        if self.role == 'worker':
            ansible_vars = [{'master_key': master_key}]

        if self.role == 'master':
            ansible_vars = [
                {'pod_network_cidr': config_model.config.pod_network_cidr},
                {'k8s_master_ip': config_model.config.controller_ip}
                # ^-- They are used as ansible vars in playbook_kubernetes_master.yml
            ]

        self.addPlaybook('blueprints/blue_k8s/config_scripts/playbook_kubernetes_common_beta.yaml', vars_=ansible_vars)

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
        return super(ConfiguratorK8sBeta, self).dump()

    def get_logpath(self):
        # return [self.conf['log_filename']]
        return []

    def custom_prometheus_exporter(self):

        return []

    def destroy(self):
        logger.info("Destroying")
        # TODO remove prometheus jobs

        # super(Configurator_AmariEPC, self).destroy()
