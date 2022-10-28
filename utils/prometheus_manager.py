import ruamel.yaml
import paramiko
#from utils.util import *
#from scp import SCPClient

'''
  'prometheus': {
    'scrap_file': 'nfvcl.yaml',
    'host': '192.168.100.10',
    'port': 27017,
    'passwd': 'root',
    'user': 'root'
  }
'''
endpoint = []

with open("config.yaml", 'r') as stream:
    try:
        nfvcl_conf = ruamel.yaml.safe_load(stream)
    except ruamel.yaml.YAMLError as exc:
        print(exc)

    # Parsing the config file
    try:
        for ep in nfvcl_conf['prometheus']:
            endpoint.append({
                    'scrap_file': ep['scrap_file'],
                    'host': ep['host'],
                    'port': ep['port'],
                    'user': ep['user'],
                    'passwd': ep['passwd']
            })
    except:
        print('exception in the configuration file parsing')


def createSSHClient(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password, allow_agent=False)

    return client

def createSCPClient(server, port, user, password):
    ssh = createSSHClient(server, port, user, password)
    #scp = SCPClient(ssh.get_transport())
    scp = ssh.open_sftp()
    return scp

def closeSCPClient(scp):
    scp.close()

class PrometheusManager():
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.jobs = [] #recover jobs from mongo?

    def findJobByTarget(self, target):
        return next((item for item in self.jobs if target in item['targets']), None)

    def findJobByLabels(self, labels):
        return next((item for item in self.jobs if item['labels'] == labels), None)

    def delTarget(self, job, target):
        job['targets'] =  [item for item in job['targets'] if target != item]

        #removing jobs without targets
        self.jobs = [item for item in self.jobs if len(item['targets']) > 0]

    def addJob(self, targets, labels):
        #job -> {tagets: ['x.x.x.x:yyy'], labels: {'name': 'value'} }
        for t in targets:
            target_job = self.findJobByTarget(t)
            if target_job is not None:
                #remove the same target from other jobs
                self.delTarget(target_job, t)
        label_job = self.findJobByLabels(labels)
        if label_job is None:
            self.jobs.append({'targets': targets, 'labels': labels})

        else:
            #the job with the right labels already exists
            for t in targets:
                label_job['targets'].append(t)

    def delJobByLabels(self, labels):
        labels.sort()
        job = self.findJobByLabels(labels)
        if job is not None:
            del job

    def delJobTargets(self, targets):
        for t in targets:
            job = self.findJobByTarget(t)
            if job is not None:
                self.delTarget(job, t)
    def dumpFile(self):
        with open('day2_files/prometheus_scraps.yaml', 'w') as f:
            f.write(ruamel.yaml.dump(self.jobs, Dumper=ruamel.yaml.RoundTripDumper, allow_unicode=True))

    def transferFile(self):
        self.dumpFile()
        try:
            for ep in self.endpoint:
                print('transfering scrap file to prometheus')
                # print(ep)
                scp = createSCPClient(ep['host'], ep['port'], ep['user'], ep['passwd'])
                scp.put('day2_files/prometheus_scraps.yaml', ep['scrap_file'])
                scp.close()
        except ValueError as err:
            print(err.args)


PrometheusMan = PrometheusManager(endpoint)
