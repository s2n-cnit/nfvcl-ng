import json
import textwrap
import uuid
from jinja2 import Environment, FileSystemLoader
from ruamel.yaml import YAML
from ruamel.yaml import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from configurators.configurator import Configurator_Base

# NOTE: here ruamel is needed just because the ansible shell module needs a multiline scalar literal block in yaml (
# i.e., shell:|)
with open("config.yaml", 'r') as stream:
    try:
        yaml = YAML()
        nfvcl_conf = yaml.load(stream)
    except YAMLError as exc:
        print(exc)

# Parsing the config file
try:
    nfvcl_ip = nfvcl_conf['nfvcl']['ip']
    nfvcl_port = nfvcl_conf['nfvcl']['port']
except Exception as e:
    raise ValueError('problem in parsing the configuration file')

nfvclURL = 'http://' + nfvcl_ip + ':' + str(nfvcl_port) + '/nfvcl_day2/day2/'
nfvclURL_postActions = 'http://' + nfvcl_ip + ':' + str(nfvcl_port) + '/nfvcl_day2/actions'

yaml = YAML()
yaml.preserve_quotes = True


class Configurator_Flex(Configurator_Base):
    def __init__(self, nsd_id, m_id, blue_id):
        # mid = 1 as first input
        global nfvclURL
        self.nsd_id = nsd_id
        self.nsd = {'member-vnfd-id': m_id}
        self.blue_id = blue_id
        self.dump_number = 1
        self.config_content = {'conf_files': [], 'playbooks': []}
        self.resetPlaybook()
        self.monitoring_tools = []

    def getID(self) -> str:
        return self.nsd_id + "_" + self.nsd['member-vnfd-id']

    def resetPlaybook(self):
        self.playbook = {'hosts': 'all', 'become': True, 'gather_facts': 'no', 'tasks': []}

    def addJinjaTemplateFile(self, filed, vars_):
        # filed is the descriptor of the file to be transferred. It should have the following keys:
        # - 'template' name of the template file (with placeholder variables) to be used
        # - 'transfer_name' (name to be used for the transfer between the OSS and the VNFD)
        # - 'name' (final name of the file within the vnf)
        # - 'path' (final path of the file within the vnf manager, i.e., within the flexcham/flexchart)
        # vocabulary is a list of {'placeholder': key, 'value': value} for translating placeholder var in template
        # elk_files
        env_path = ""
        for folder in filed['template'].split('/')[:-1]:
            env_path += "{}/".format(folder)
        template_filename = filed['template'].split('/')[-1]
        env = Environment(loader=FileSystemLoader(env_path),
                          extensions=['jinja2_ansible_filters.AnsibleCoreFiltersExtension'])
        template = env.get_template(template_filename)
        data = template.render(confvar=vars_)

        # with open('day2_files/' + filed['transfer_name'], 'w') as file:
        with open('day2_files/' + filed['transfer_name'], 'w') as file:
            file.write(data)
            file.close()
        # add the produced file, to the list of elk_files to be downloaded by the VNFM
        self.config_content['conf_files'].append(
            {'src': nfvclURL + filed['transfer_name'], 'name': filed['name']})
        self.playbook['tasks'].append({
            'name': 'Configuration file copy from the VNFM to the VNF',
            'copy': {'src': filed['name'], 'dest': filed['path'], 'mode': 664, 'force': 'yes', 'backup': 'yes'}
        })

    def addTemplateFile(self, filed, vocabulary):
        # filed is the descriptor of the file to be transferred. It should have the following keys:
        # - 'template' name of the template file (with placeholder variables) to be used
        # - 'transfer_name' (name to be used for the transfer between the OSS and the VNFD)
        # - 'name' (final name of the file within the vnf)
        # - 'path' (final path of the file within the VNF)
        # vocabulary is a list of {'placeholder': key, 'value': value} for translating
        # placeholder var in template elk_files
        with open(filed['template'], 'r+') as file:
            data = file.read()
            for v in vocabulary:
                data = data.replace(v['placeholder'], v['value'])

        with open('day2_files/' + filed['transfer_name'], 'w') as file:
            file.write(data)
            file.close()
        # add the produced file, to the list of elk_files to be downloaded by the VNFM
        self.config_content['conf_files'].append(
            {'src': nfvclURL + filed['transfer_name'], 'name': filed['name']})
        self.playbook['tasks'].append({
            'name': 'Configuration file copy from the VNFM to the VNF',
            'copy': {'src': filed['name'], 'dest': filed['path'], 'mode': 664, 'force': 'yes', 'backup': 'yes'}
        })

    def addPlaybook(self, playbook_file: str, vars_=None):
        # print(os.path.dirname(os.path.abspath(__file__)) + '/' + playbook_file)
        with open(playbook_file, 'r+') as stream_:
            plays_ = yaml.load(stream_)
            if not plays_:
                raise ValueError('playbook {} has not plays!'.format(playbook_file))
            self.playbook['tasks'] = plays_[0]['tasks']

            if len(plays_) > 1:
                print("WARNING! the playbook {} contains multiple plays. Only the first one will be considered."
                      .format(playbook_file))
            if vars_ is not None:
                self.playbook['vars'] = vars_
            else:
                self.playbook['vars'] = plays_[0]['vars']

            if 'gather_facts' not in self.playbook:
                self.playbook['gather_facts'] = 'no'

    def appendPbTasks(self, playbook_file: str, jinja: bool = False):
        with open(playbook_file, 'r+') as stream_:
            # yaml = YAML()
            #
            if jinja:
                yaml_jinja = YAML(typ='jinja2')
                plays_ = yaml_jinja.load(stream_)
            else:
                plays_ = yaml.load(stream_)
            if not plays_:
                raise ValueError('playbook {} has not plays!'.format(playbook_file))
            if len(plays_) > 1:
                print("WARNING! the playbook {} contains multiple plays. Only the first one will be considered."
                      .format(playbook_file))
            for task in plays_[0]['tasks']:
                self.playbook['tasks'].append(task)

    def appendJinjaPbTasks(self, playbook_file: str, vars_):
        env_path = ""
        for folder in playbook_file.split('/')[:-1]:
            env_path += "{}/".format(folder)
        filename = playbook_file.split('/')[-1]
        env = Environment(loader=FileSystemLoader(env_path),
                          extensions=['jinja2_ansible_filters.AnsibleCoreFiltersExtension'])
        template = env.get_template(filename)
        yaml_jinja = YAML(typ='jinja2')
        plays_ = yaml_jinja.load( template.render(confvar=vars_) )
        if not plays_:
            raise ValueError('playbook {} has not plays!'.format(playbook_file))
        if len(plays_) > 1:
            print("WARNING! the playbook {} contains multiple plays. Only the first one will be considered."
                  .format(playbook_file))
        for task in plays_[0]['tasks']:
            self.playbook['tasks'].append(task)

    def addConfFile(self, filed):
        self.config_content['conf_files'].append(
            {'src': nfvclURL + filed['transfer_name'], 'name': filed['name']})
        self.playbook['tasks'].append({
            'name': 'Configuration file copy from the VNFM to the VNF',
            'copy': {'src': filed['name'], 'dest': filed['path'], 'mode': 664, 'force': 'yes', 'backup': 'yes'}
        })

    def addShellCmds(self, filed, vocabulary):
        # filed is the descriptor of the shell file to be used in the playbook. It should have the following keys:
        # - 'template' name of the shell template file (with placeholder variables) to be used
        # vocabulary is a list of {'placeholder': key, 'value': value} for translating placeholder var in template elk_files
        with open(filed['template'], 'r+') as file:
            data = file.read()
            for v in vocabulary:
                data = data.replace(v['placeholder'], v['value'])

        # add the produced file, to the list of elk_files to be downloaded by the VNFM
        self.playbook['tasks'].append({
            'name': 'Shell Commands',
            'shell': LiteralScalarString(textwrap.dedent(data)),
            'args': {'executable': '/bin/bash'}
        })

    def addPackage(self, pkg_name: str):
        self.playbook['tasks'].append({
            'name': 'install package',
            'package': {
                'name': pkg_name,
                'state': 'present'
            }
        })

    def addRestCmd(self, url: str, message, method, status):
        """
        name: Create a JIRA issue
          uri:
            url: https://your.jira.example.com/rest/api/2/issue/
            user: your_username
            password: your_pass
            method: POST
            body: "{{ lookup('file','issue.json') }}"
            force_basic_auth: yes
            status_code: 201
            body_format: json
        """
        self.playbook['tasks'].append({
            'name': 'REST command',
            'uri': {
                'url': url,
                'method': method,
                'body': json.dumps(message),
                'status_code': status,
                'body_format': 'json'
            }
        })

    def dumpAnsibleFile(self, prio, transfer_name):
        with open('day2_files/' + transfer_name + "_step" + str(self.dump_number) + ".yaml", 'w') as file:
            # yaml = YAML()
            try:
                yaml.dump([self.playbook], file)
            except Exception as e:
                print(e)
                print(self.playbook)
        self.config_content['playbooks'].append(
            {
                'prio': prio,
                'src': nfvclURL + transfer_name + "_step" + str(self.dump_number) + ".yaml",
                'name': transfer_name + "_step" + str(self.dump_number) + ".yaml"
            }
        )

    def dump(self):
        # adding an action id to be passed to the charm
        # we will use it to get results back (stdout)
        self.config_content['action_id'] = str(uuid.uuid4())
        self.config_content['post_url'] = nfvclURL_postActions
        self.config_content['nsd_id'] = self.nsd_id
        self.config_content['vnfd_id'] = self.nsd['member-vnfd-id']
        self.config_content['blue_id'] = self.blue_id

        res = self.dump_()

        # config_content is flushed/reset by dump_, we need to recreate the arrays
        self.config_content = {'conf_files': [], 'playbooks': []}
        self.resetPlaybook()
        self.dump_number += 1
        return res

    def get_logpath(self):
        return []

    def enable_elk(self, args):
        # in this version only the filebeat is supported
        self.monitoring_tools.append("elk")
        app_logfile = self.get_logpath()

        placeholder_dict = [
            {'placeholder': '__LOGSTASH_IP__', 'value': args['logstash_ip']},
            {'placeholder': '__LOGSTASH_PORT__', 'value': args['logstash_port']},
            {'placeholder': '__KIBANA_IP__', 'value': args['kibana_ip']},
            {'placeholder': '__KIBANA_PORT__', 'value': args['kibana_port']}
        ]
        self.addTemplateFile(
            {'template': 'config_templates/elk_filebeat.conf',
             'path': '/etc/',
             'transfer_name': 'elk_filebeat_' + self.getID() + '.conf',
             'name': 'filebeat.yaml'
             }, placeholder_dict)

        self.addShellCmds({'template': 'config_templates/elk_filebeat.shell'}, placeholder_dict)
        return self.dump()

    def disable_elk(self):
        if "elk" in self.monitoring_tools:
            self.addShellCmds({'template': 'config_templates/disable_elk_filebeat.shell'}, [])
            self.monitoring_tools.remove("elk")
            return self.dump()

    def custom_prometheus_exporter(self):
        # virtual function
        return []

    def enable_prometheus(self):
        # global PrometheusMan

        self.monitoring_tools.append("prometheus")
        targets = []
        # install the exporters (package or custom)

        # node exporter should be always present for flex based VNF
        self.addPackage('prometheus-node-exporter')
        targets.append(self.mng_ip + ':9100')
        for t in self.custom_prometheus_exporter():
            targets.append(t)

        labels = {'nsd_id': str(self.nsd_id), 'vnf_id': str(self.nsd['member-vnfd-id']), 'type': str(self.type)}

        if hasattr(self, 'conf'):
            if 'plmn' in self.conf:
                labels['plmn'] = str(self.conf['plmn'])

        # TODO enable adding job to prometheus in automatic way
        # PrometheusMan.addJob(targets, labels)

        return self.dump()

    def disable_prometheus(self):
        if "prometheus" in self.monitoring_tools:
            # self.addShellCmds({'template': 'config_templates/disable_elk_filebeat.shell'}, placeholder_dict)
            self.monitoring_tools.remove("prometheus")
            # FIXME add shell commands to stop the screen (in the child class)
