#!/usr/bin/env python3
import sys, yaml, urllib.request, urllib.parse, json, requests

sys.path.append("lib")

from charms.osm.sshproxy import SSHProxyCharm
from ops.main import main
# import charms.osm.libansible
from charms.osm import libansible


class FlexCharmVyOS(SSHProxyCharm):
    def __init__(self, framework, key):
        super().__init__(framework, key)

        # Listen to charm events
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        # self.framework.observe(self.on.upgrade_charm, self.on_upgrade_charm)

        # Listen to the touch action event
        self.framework.observe(self.on.flexops_action, self.flexops)

    def on_config_changed(self, event):
        """Handle changes in configuration"""
        super().on_config_changed(event)

    def on_install(self, event):
        """Called when the charm is being installed"""
        super().on_install(event)
        libansible.install_ansible_support()


    def on_start(self, event):
        """Called when the charm is being started"""
        super().on_start(event)

    def log_to_file(self, content):
        debug_f = open('/tmp/charm.log', 'a+')
        # debug_f.write("****** config-content")
        debug_f.write(content)
        debug_f.close()

    def flexops(self, event):
        if self.model.unit.is_leader():
            try:
                self.log_to_file('--------- flexops init\n')
                hostname = self.model.config["ssh-hostname"]
                user = self.model.config["ssh-username"]
                passwd = self.model.config["ssh-password"]

                self.log_to_file('--------- config parsing\n')
                config = yaml.load(event.params['config-content'])
                # self.log_to_file(config)

                action_id = config['action_id']
                nsd_id = config['nsd_id']
                vnfd_id = config['vnfd_id']
                blue_id = config['blue_id']
                post_url = config['post_url']
                conf_files = config['conf_files']

                playbooks = sorted(config['playbooks'], key=lambda x: x['prio'])
                self.log_to_file('--------- downloading\n')
                for file_ in conf_files:
                    result = urllib.request.urlretrieve(file_['src'], '/var/lib/juju/agents/' + file_['name'])
                    self.log_to_file('{} --> {}\n'.format(file_['src'], file_['name']))

                for file_ in playbooks:
                    result = urllib.request.urlretrieve(file_['src'], '/var/lib/juju/agents/' + file_['name'])
                    # self.log_to_file('{}'.format(result))
                    self.log_to_file('{} --> {}\n'.format(file_['src'], file_['name']))

                self.log_to_file('--------- applying\n')
                result = []
                for p in playbooks:
                    result_ = libansible.execute_playbook(p['name'], hostname, user, passwd, {}).decode("utf-8")
                    self.log_to_file("{}\n".format(result_))

                    # looking for the line where the json stdout starts
                    line_index = -1
                    for line_count, line_content in enumerate(result_.split('\n'), 0):
                        if len(line_content) > 0:
                            if line_content[0] == '{':
                                line_index = line_count
                                break

                    json_string = ""
                    for s in result_.split('\n')[line_index:]:
                        json_string += s + '\n'
                    result.append({'playbook': p['name'], 'stdout': json.loads(json_string)})

                # generate post method to the nfvcl
                post_message = {
                    'result': result,
                    'action_id': action_id,
                    'nsd_id': nsd_id,
                    'vnfd_id': vnfd_id,
                    'blue_id': blue_id
                }

                r = requests.post(post_url, json=json.dumps(post_message))
                self.log_to_file("{}\n".format(r))
                """
                data = urllib.parse.urlencode(post_message).encode()
                req = urllib.request.Request(post_url, data=data)  # this will make the method "POST"
                resp = urllib.request.urlopen(req)
                self.log_to_file("{}\n".format(resp))
                """

                event.set_results({"output": action_id})
                self.log_to_file('--------- done\n')
            except Exception as e:
                event.fail("Action failed {}.".format(e))
                self.log_to_file("Action failed {}.\n".format(e))
        else:
            event.fail("Unit is not leader")


if __name__ == "__main__":
    main(FlexCharmVyOS)
