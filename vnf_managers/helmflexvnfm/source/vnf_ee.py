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
import logging
from logging.handlers import RotatingFileHandler
import coloredlogs
import verboselogs

from osm_ee.exceptions import VnfException
import osm_ee.util.util_ee as util_ee
#import osm_ee.util.util_ansible as util_ansible

############## LOGGER #################
#######################################
_log_level = logging.DEBUG


def set_log_level(level):
    """
    Set the level of the loggers that will be created. Old loggers will have the old value.
    Args:
        level: the level to be set
    """
    global _log_level
    _log_level = level


coloredlog_format_string = "%(asctime)s [%(name)-20.20s][%(threadName)-10.10s] [%(levelname)8s] %(message)s"

level_styles = {
    'spam': {'color': 'green', 'faint': True},
    'debug': {'color': 241},
    'verbose': {'color': 'blue'},
    'info': {},
    'notice': {'color': 'magenta'},
    'warning': {'color': 'yellow'},
    'success': {'color': 'green', 'bold': True},
    'error': {'color': 'red'},
    'critical': {'color': 'red', 'bold': True}
}

field_styles = {
    'asctime': {'color': 247},
    'hostname': {'color': 'magenta'},
    'levelname': {'color': 'cyan', 'bold': True},
    'name': {'color': 33},
    'programname': {'color': 'cyan'},
    'username': {'color': 'yellow'},
    'devicename': {'color': 34}
}
coloredlog_formatter = coloredlogs.ColoredFormatter(
    fmt=coloredlog_format_string,
    field_styles=field_styles,
    level_styles=level_styles
)

ROOT_LOGGER_NAME = "RootLogger"
formatter = logging.Formatter(coloredlog_format_string)


def create_logger(name: str, ov_log_level: int = None) -> logging.Logger:
    """
    Creates a logger outputting on: console, redis, and on file.
    In this way, an external entity to the NFVCL is able to observe what is going on.
    The log file allows permanent info in case of failure (NB on next restart the log file is overwritten)

    Args:
        name: The name of the logger to be displayed in logs.
        ov_log_level: Can be used to override global log level

    Returns:

        The created logger
    """
    # If defined use override log level, otherwise the global.
    if ov_log_level is not None:
        local_log_level = ov_log_level
    else:
        local_log_level = _log_level

    logger = verboselogs.VerboseLogger(name)
    logger.parent = logging.getLogger(ROOT_LOGGER_NAME)

    # Adding file handler to post log into file
    # w = every restart log is cleaned
    log_file_handler = RotatingFileHandler("nfvmanager.log", maxBytes=10000000, backupCount=4)
    log_file_handler.setLevel(local_log_level)
    log_file_handler.setFormatter(formatter)
    logger.addHandler(log_file_handler)

    coloredlogs.install(
        level=local_log_level,
        logger=logger,
        fmt=coloredlog_format_string,
        field_styles=field_styles,
        level_styles=level_styles
    )

    return logger

def mod_logger(logger: logging.Logger):
    """
    This method takes an existing logger and mod it.
    """
    coloredlogs.install(
        level=_log_level,
        logger=logger,
        fmt=coloredlog_format_string,
        field_styles=field_styles,
        level_styles=level_styles
    )

global_logger = create_logger("VNF-Manager", logging.DEBUG)

#############VNF MANAGER ####################
#############################################

def wait_for_ssh_to_be_ready(host: str, port: int, user: str, passwd: str, timeout: int, retry_interval: float) -> bool:
    global_logger.debug(f"Starting SSH connection to {host}:{port} as user <{user}> and passwd <{passwd}>. Timeout is {timeout}, retry interval is {retry_interval}")
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        try:
            client.connect(host, port, username=user, password=passwd, allow_agent=False, look_for_keys=False)
            global_logger.debug('SSH transport is available!')
            client.close()
            return True
        except paramiko.ssh_exception.SSHException as e:
            # socket is open, but not SSH service responded
            global_logger.debug("socket is open, but not SSH service responded")
            global_logger.debug(e)
            time.sleep(retry_interval)
            continue

        except paramiko.ssh_exception.NoValidConnectionsError as e:
            global_logger.debug('SSH transport is not ready...')
            time.sleep(retry_interval)
            continue
    return False


class VnfEE:

    PLAYBOOK_PATH = "/tmp/"
    ANSIBLE_CONFIG_PATH = "/etc/ansible/ansible.cfg"
    ANSIBLE_INVENTORY_PATH = "/etc/ansible/hosts"

    def __init__(self, config_params):
        self.logger = global_logger
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
            config = yaml.safe_load(params['config-content'])
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
                    5):
                self.logger.error("Cannot establish connection to ssh server: {}".format(self.config_params["ssh-hostname"]))
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
