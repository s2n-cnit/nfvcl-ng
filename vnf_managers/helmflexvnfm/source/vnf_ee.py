##
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##

import asyncio
import logging
import yaml
import urllib
import json
import urllib.request
import requests
import traceback
import paramiko
import time


from osm_ee.exceptions import VnfException

import osm_ee.util.util_ee as util_ee
#import osm_ee.util.util_ansible as util_ansible

def wait_for_ssh_to_be_ready(host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float) -> bool:
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        try:
            client.connect(host, port, username=user, password=passwd, allow_agent=False, look_for_keys=False)
            print('SSH transport is available!')
            client.close()
            return True
        except paramiko.ssh_exception.SSHException as e:
            # socket is open, but not SSH service responded
            print("socket is open, but not SSH service responded")
            print(e)
            time.sleep(retry_interval)
            continue

        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print('SSH transport is not ready...')
            time.sleep(retry_interval)
            continue
    return False


class VnfEE:
    
    PLAYBOOK_PATH = "/tmp/"
    ANSIBLE_CONFIG_PATH = "/etc/ansible/ansible.cfg"
    ANSIBLE_INVENTORY_PATH = "/etc/ansible/hosts"

    def __init__(self, config_params):
        self.logger = logging.getLogger('osm_ee.vnf')
        self.config_params = config_params

    async def config(self, id_, params):
        self.logger.debug("Execute action config params: {}".format(params))
        # Config action is special, params are merged with previous config calls
        self.config_params.update(params)
        required_params = ["ssh-hostname"]
        self._check_required_params(self.config_params, required_params)
        yield "OK", "Configured"

    async def sleep(self, id_, params):
        self.logger.debug("Execute action sleep, params: {}".format(params))

        for i in range(3):
            await asyncio.sleep(5)
            self.logger.debug("Temporal result return, params: {}".format(params))
            yield "PROCESSING", f"Processing {i} action id {id_}"
        yield "OK", f"Processed action id {id_}"

    async def flexops(self, id_, params):
        self.logger.debug("Execute action ansible_playbook, params: {} --- id: {}".format(params, id_))

        with open(self.ANSIBLE_CONFIG_PATH, "w") as f:
            f.write(
                "[defaults]\nstdout_callback = json\nbin_ansible_callbacks = True\nhost_key_checking = False\nlog_path = /var/log/ansible.log\n"
            )

        try:
            self._check_required_params(params, ['config-content'])

            # params["ansible_user"] = self.config_params["ssh-username"]
            # params["ansible_password"] = self.config_params["ssh-password"]

            # inventory = self.config_params["ssh-hostname"] + ","

            self.logger.debug('creating Ansible inventory file')
            with open(self.ANSIBLE_INVENTORY_PATH, "w") as f:
                h1 = "host ansible_host={0} ansible_user={1} ansible_password={2}\n".format(
                    self.config_params["ssh-hostname"],
                    self.config_params["ssh-username"],
                    self.config_params["ssh-password"]
                )
                f.write(h1)

            self.logger.debug('config-content parsing\n')
            config = yaml.load(params['config-content'])
            # self.log_to_file(config)

            action_id = config['action_id']
            nsd_id = config['nsd_id']
            vnfd_id = config['vnfd_id']
            blue_id = config['blue_id']
            post_url = config['post_url']
            conf_files = config['conf_files']

            playbooks = sorted(config['playbooks'], key=lambda x: x['prio'])
            self.logger.debug('downloading playbooks and config files from NFVCL')
            for file_ in conf_files + playbooks:
                self.logger.debug("Retrieving file {} from {}".format(file_['name'], file_['src']))
                result = urllib.request.urlretrieve(file_['src'], '{}/{}'.format(self.PLAYBOOK_PATH, file_['name']))
                self.logger.debug('{} --> {}\n'.format(file_['src'], file_['name']))

            self.logger.debug("checking SSH status")
            if not wait_for_ssh_to_be_ready(
                    self.config_params["ssh-hostname"],
                    22,
                    self.config_params["ssh-username"],
                    self.config_params["ssh-password"],
                    300,
                    30):
                raise ValueError('SSH connection not available')

            self.logger.debug('Applying configurations and commands')
            result = []

            for pb in playbooks:
                command = 'ansible-playbook {}/{}'.format(self.PLAYBOOK_PATH, pb['name'])
                self.logger.debug("Command to be executed: {}".format(command))
                return_code, stdout, stderr = await util_ee.local_async_exec(command)
                stdoutput = stdout.decode("utf-8")  #.split('\n')
                stderror = stderr.decode("utf-8")
                self.logger.debug("return_code: {}, stdout: {}, stderr: {}".format(return_code, stdoutput, stderror))
                # remove non json stdout lines (e.g., from the ansible pause modules)
                start_position = stdoutput.find('{')
                json_string = stdoutput[start_position:]
                # json_string = "".join(stdoutput).replace('\\', '\\\\')
                # json.loads(json_string)
                result.append({'playbook': pb['name'], 'stdout': json.loads(json_string), 'stderr': stderror})

            # generate post method to the nfvcl
            post_message = {
                'result': result,
                'action_id': action_id,
                'nsd_id': nsd_id,
                'vnfd_id': vnfd_id,
                'blue_id': blue_id
            }
            self.logger.info("POST message body: {}".format(json.dumps(post_message)))
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            r = requests.post(post_url, json=post_message, headers=headers)
            self.logger.info("POST message: {} - {}".format(r.status_code, r.text))

            yield "OK", "Action ID: {}".format(post_message['action_id'])
        except Exception as e:
            self.logger.error(traceback.format_tb(e.__traceback__))
            self.logger.error("Error executing flexops: {}".format(repr(e)))
            yield "ERROR", str(e) + "\n".join(traceback.format_tb(e.__traceback__))
        

    @staticmethod
    def _check_required_params(params, required_params):
        for required_param in required_params:
            if required_param not in params:
                raise VnfException("Missing required param: {}".format(required_param))
