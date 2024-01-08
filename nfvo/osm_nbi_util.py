import json
import time
import requests
import ruamel
import os
import tarfile
import yaml
from pathlib import Path
from typing import List
from urllib3.exceptions import InsecureRequestWarning
from models.k8s.topology_k8s_model import K8sModel
from utils.log import create_logger
from utils.util import get_nfvcl_config
from re import match

# Disable the InsecureRequestWarning for the requests to OSM
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# create logger
logger = create_logger('OSM NBI')


def nsd_build_package(name, nsd):
    # checking if nsd_packages folder is existing
    if os.path.isdir('/tmp/nsd_packages/') is False:
        os.mkdir('/tmp/nsd_packages/', 0o755)

    logger.info("now building NSD " + name)
    path = '/tmp/nsd_packages/' + name + '/'
    if os.path.isdir(path) is False:
        os.mkdir(path, 0o755)
        Path(path + name + '.yaml').touch()
    with open(path + name + '.yaml', "w+") as nsd_file:
        content = ruamel.yaml.dump(
            nsd, Dumper=ruamel.yaml.RoundTripDumper, allow_unicode=True, default_flow_style=False)
        nsd_file.write(content)
    nsd_file.close()
    if os.path.isfile('/tmp/nsd_packages/' + name + '.tar.gz') is True:
        os.remove('/tmp/nsd_packages/' + name + '.tar.gz')
    # os.chdir('/tmp/nsd_packages/')
    with tarfile.open('/tmp/nsd_packages/' + name + '.tar.gz', "w:gz") as tar:
        tar.add('/tmp/nsd_packages/' + name, arcname=name)
    # os.chdir('../..')


def check_authorization(decorated_function):
    """
    Decorator! Check if the token is still valid before API call to OSM. If not it requests a new token
    Args:
        decorated_function: The function to be decorated

    Returns:
        The wrapper
    """
    def wrapper(*args):
        # args[0] when called from an object function ( example(self, arg1, arg...) ) is the object itself
        osm_nbi_utils: NbiUtil = args[0]
        response = requests.get(osm_nbi_utils.token_url, headers=osm_nbi_utils.headers, verify=False)

        # If 401 == unauthorized. Requesting a new token.
        if response.status_code == 401:
            logger.debug("Token was not valid, requiring a new one")
            osm_nbi_utils.new_token()
        return decorated_function(*args)

    return wrapper


def check_rest_response(response: requests.Response) -> bool:
    """
    Checks that the response is positive (OK, ACCEPTED, CREATED, NO_CONTENT)
    Args:
        response: The response to be analyzed

    Returns:
        True if the response is positive, False otherwise

    """
    if response.status_code in (requests.codes.ok, requests.codes.accepted, requests.codes.created,
                                requests.codes.no_content):
        return True
    else:
        logger.error(f"Response from {response.url}: {response.status_code} - {response.reason}")
        logger.error(response.text)
        return False


class NbiUtil:

    def __init__(self, username: str = "admin", password: str = "admin", project: str = "admin", osm_ip: str = None,
                 osm_port: str = '9999', vim_account_id: str = ""):

        self.username = username
        self.password = password
        self.project = project

        if osm_ip is None:
            raise ValueError("OSM IP address not available")
        else:
            self.osm_nbi_url = "https://{}:{}/osm".format(osm_ip, osm_port)

        self.vim_account_id = vim_account_id
        self.base_url = self.osm_nbi_url
        self.token_url = "{0}/admin/v1/tokens".format(self.base_url)
        self.instantiate_url = self.osm_nbi_url + "/nslcm/v1/ns_instances"
        self.ns_descriptors_url = "{0}/nsd/v1/ns_descriptors".format(self.base_url)
        self.vnf_descriptors_url = "{0}/vnfpkgm/v1/vnf_packages".format(self.base_url)

        self.headers = {"Accept": "application/json"}
        self.new_token()

    def new_token(self):
        """
        Requires a new token for interacting with OSM and update it in the object headers to be used in API calls.

        Raises: ValueError in case the token could not be retrieved
        """
        response = requests.post(self.token_url,
                                 json={"username": self.username, "password": self.password},
                                 headers=self.headers,
                                 verify=False)
        if response.status_code is not requests.codes.ok:
            logger.error(response.text)
            raise ValueError("OSM auth token request not successful")
        token = json.loads(response.text).get("id")
        self.headers.update({"Authorization": "Bearer {0}".format(token)})

    # get_x generic method for http GET messages
    @check_authorization
    def get_x(self, rest_url: str) -> requests.Response:
        url = "{0}{1}".format(self.osm_nbi_url, rest_url)
        try:
            r = requests.get(url, params=None, verify=False, stream=True, headers=self.headers)
            return r
        except Exception as e:
            logger.error("ERROR - get_x: ", e)
            raise ValueError("{} --- {}".format(r.status_code, r.reason))

    # get_x generic method for http POST messages
    @check_authorization
    def post_x(self, data, rest_url: str) -> requests.Response:
        headers = dict(self.headers)
        headers["Content-type"] = "application/json"
        headers["Accept"] = "application/json"
        url = "{0}{1}".format(self.osm_nbi_url, rest_url)
        # logger.debug(json.dumps(data))
        try:
            r = requests.post(url, json=data, params=None, verify=False, stream=True, headers=headers)
            return r
        except Exception as e:
            logger.error("ERROR - post_x: ", e)
            return r

    @check_authorization
    def post_package(self, data, pkg_name: str, rest_url: str) -> requests.Response:
        headers = dict(self.headers)
        headers["Content-type"] = "application/gzip"
        headers["Accept"] = "application/json"
        headers['Content-Filename'] = pkg_name
        url = "{0}{1}".format(self.osm_nbi_url, rest_url)
        try:
            r = requests.post(url, data, params=None, verify=False, headers=headers)
            return r
        except Exception as e:
            logger.error("ERROR - post_package: ", e)
            return r

    @check_authorization
    def delete_x(self, url: str, force: bool = False) -> requests.Response:
        query_path = ''
        if force:
            query_path = '?FORCE=true'
        _url = "{0}{1}{2}".format(self.base_url, url, query_path)
        # logger.debug("delete OSM URL " + _url)
        try:
            r = requests.delete(_url, params=None, verify=False, headers=self.headers)
            # logger.debug("delete OSM status code " + str(r.status_code))
            # logger.debug("delete OSM text " + r.text)
            return r
        except Exception as e:
            logger.error(str(e))

            return r

    # Network Service Instances ###########################################################################
    def get_nsi_list(self) -> dict:
        res = self.get_x("/nslcm/v1/ns_instances")
        if check_rest_response(res):
            return res.json()

    def check_ns_instance(self, ns_id: str) -> dict:
        """
        Retrieve a NS from OSM after checking if the operational status is ok.
        Args:
            ns_id: The ID of the network service

        Returns:
            The network service if ok.s
        """
        if ns_id is None or len(ns_id) <= 0:
            msg = "The ns_id is empty, all NS would be retrieved instead of 1"
            logger.error(msg)
            raise ValueError(msg)
        res = self.get_x("/nslcm/v1/ns_instances/{}".format(ns_id))
        if check_rest_response(res):
            nsr = res.json()
            if "operational-status" not in nsr:
                raise ValueError(str(nsr["detailed-status"]))
            if nsr["operational-status"] == "failed":
                raise ValueError(str(nsr["detailed-status"]))
            return nsr

    def post_ns_instance(self, nsd_id, name, description, vim_account_id=None):
        # start_time = datetime.datetime.now()
        if vim_account_id is None:
            raise ValueError("VIM id not expressed to the NBI")

        data = {
            "nsdId": nsd_id,
            "nsName": name,
            "nsDescription": description,
            "vimAccountId": vim_account_id
        }
        response1 = self.post_x(data, "/nslcm/v1/ns_instances")
        if not check_rest_response(response1):
            logger.error(response1)
            raise ValueError("error in NS instantiation at NBI")
        instantiation_data = json.loads(response1.text)
        ns_id = instantiation_data["id"]

        response2 = self.post_x(data, "/nslcm/v1/ns_instances/{}/instantiate".format(ns_id))
        r_text = json.loads(response2.text)
        if not check_rest_response(response2):
            self.ns_delete(ns_id)
            raise ValueError(str(r_text['detail']))

        # Check the service status and loop until it's configured
        while True:
            nsr = self.check_ns_instance(ns_id)
            if nsr["config-status"] == "configured":
                break
            if nsr["operational-status"] == "failed":
                raise ValueError(str(nsr["detailed-status"]))
            time.sleep(5)
        # end_time = datetime.datetime.now()
        return ns_id, 200

    def ns_delete(self, ns_id: str, force: bool = False) -> dict:
        res = self.delete_x("/nslcm/v1/ns_instances_content/{}".format(ns_id), force)
        if res.status_code == requests.codes.no_content:
            return {'error': True, 'data': {}}
        return {
            'error': not check_rest_response(res),
            'data': json.loads(res.text) if res.text is not None else {}
        }

    def instantiate_ns(self, nsd_id: str, name: str, description: str, vim_account_id: str, ns_config=None):
        ns = ns_config
        ns['nsdId'] = nsd_id
        ns['nsName'] = name
        ns['nsDescription'] = description
        ns['vimAccountId'] = vim_account_id
        # r = self.post_x(ns, "/nslcm/v1/ns_instances_content")
        # create instance
        r = self.post_x(ns, "/nslcm/v1/ns_instances")
        if r.status_code == requests.codes.created:
            # logger.debug(r.text)
            ns_id = json.loads(r.text)['id']
            # logger.debug('NS instance {} created, preparing to run'.format(ns_id))
            # run the instance
            r2 = self.post_x(ns, "/nslcm/v1/ns_instances/{}/instantiate".format(ns_id))
            # r2 does not contains the id of the ns instance, but of the bound worker... returning the data in r
            return {'error': not check_rest_response(r2), 'data': json.loads(r.text) if r.text is not None else {}}

        return {'error': not check_rest_response(r), 'data': json.loads(r.text) if r.text is not None else {}}

    # Network Service Descriptors ###########################################################################
    def nsd_delete(self, nsd_id):
        r = self.delete_x("/nsd/v1/ns_descriptors/{}".format(nsd_id))
        return {'error': not check_rest_response(r),  # 'data': json.loads(r.text) if r.text is not None else {},
                'error_code': r.status_code}

    def nsd_onboard(self, pkg_name):
        data = open('/tmp/nsd_packages/' + pkg_name + '.tar.gz', 'rb')
        r = self.post_package(data, pkg_name + '.tar.gz', "/nsd/v1/ns_descriptors_content/")

        return {
            'error': not check_rest_response(r),
            'data': json.loads(r.text) if r.text is not None else None,
            'error_code': r.status_code
        }

    def nsd_reonboard(self, pkg_name):
        # 409 is :requests.codes.conflict
        r = self.nsd_onboard(pkg_name)
        if r['error'] is True and r['error_code'] == 409:
            nsd_id, status = self.get_nsd_by_name(pkg_name)
            r = self.nsd_delete(nsd_id)
            if r['error'] is True and r['error_code'] == 409:
                return r
            r = self.nsd_onboard(pkg_name)
        return r

    def get_nsd(self, nsd_id=None):
        url = self.ns_descriptors_url
        if nsd_id:
            url = url + "/" + str(nsd_id)
        r = self.get_x(url)
        return r.json() if r.text is not None else {}, r.status_code

    def get_nsd_by_name(self, name: str):
        r = self.get_x(self.ns_descriptors_url)
        if check_rest_response(r):
            for nsd in r.json():
                if nsd["name"] == name:
                    return nsd['_id'], 200
        return [], 404

    def get_nsd_list(self) -> dict:
        """
        Return a list of NSD present on OSM
        Returns:
            a list of NSD present on OSM
        """
        res = self.get_x("/nsd/v1/ns_descriptors")
        if check_rest_response(res):
            return res.json()

    # Virtual Network Function Descriptors ###################################################################
    def get_vnfd_list(self) -> dict:
        res = self.get_x("/vnfpkgm/v1/vnf_packages")
        if check_rest_response(res):
            return res.json()

    def vnfd_onboard(self, pkg_name):
        data = open('/tmp/vnf_packages/' + pkg_name + '.tar.gz', 'rb')
        r = self.post_package(data, pkg_name + '.tar.gz', "/vnfpkgm/v1/vnf_packages_content")

        return {
            'error': not check_rest_response(r),
            'data': json.loads(r.text) if r.text is not None else None,
            'error_code': r.status_code
        }

    def get_vnfd_detail(self, vnfd_id: str) -> dict:
        r = self.get_x("/vnfpkgm/v1/vnf_packages/{}".format(vnfd_id))
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("INFO - vnfd {} not found".format(vnfd_id))
            return {}

    def delete_vnfd(self, vnfd_id: str) -> bool:
        r = self.delete_x("/vnfpkgm/v1/vnf_packages/{}".format(vnfd_id))
        if check_rest_response(r):
            return True
        else:
            logger.error("INFO - vnfd {} not found".format(vnfd_id))
            return False

    # Virtual Network Function Instances #####################################################################
    def get_vnfi_list(self, ns_id: str) -> list:
        r = self.get_x("/nslcm/v1/vnf_instances?nsr-id-ref={}".format(ns_id))
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("INFO - vnfi list not found")
            return []

    def get_all_vnfi(self) -> list:
        r = self.get_x("/nslcm/v1/vnf_instances")
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("INFO - vnfi list not found")
            return []

    def get_vnfi_detail(self, vnfi_id: str) -> dict:
        r = self.get_x("/nslcm/v1/vnf_instances/{}".format(vnfi_id))
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("VNFI {} not found!".format(vnfi_id))
            return {}

    # Day2 primitives ###########################################################################################
    def get_subscriptions(self):
        r = self.get_x("/nslcm/v1/subscriptions")
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("Get subscription error: ".format(r.reason))
            return {}

    def delete_subscriptions(self, subscription_id: str) -> bool:
        r = self.delete_x("/nslcm/v1/subscriptions/{}".format(subscription_id))
        if check_rest_response(r):
            return True
        else:
            logger.error("Subscription {} not found!".format(subscription_id))
            return False

    def subscribe_ns_notifications(self, nsi: str, callback_uri: str):
        data = {
            "filter": {
                # "nsInstanceSubscriptionFilter": {'nsInstanceIds': [nsi]},
                # "notificationTypes": ["NsLcmOperationOccurrenceNotification"],
                # "nsInstanceSubscriptionFilter": {'nsInstanceIds': [nsi]},
                "notificationTypes": ["NsChangeNotification"],
                # "notificationTypes": [NsIdentifierCreationNotification, NsIdentifierDeletionNotification, NsLcmOperationOccurrenceNotification, NsChangeNotification],
                # "operationTypes": ['INSTANTIATE', 'SCALE', 'TERMINATE', 'UPDATE', 'HEAL'],
                # "operationTypes": ['INSTANTIATE'],
                # "operationStates": ['ANY'],
                "nsComponentTypes": ['NS'],
                "lcmOpNameImpactingNsComponent": ['NS_INSTANTIATE'],
                "lcmOpOccStatusImpactingNsComponent": ['COMPLETED'],
                # "operationStates": ['PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'FAILED_TEMP',
                #                    'ROLLING_BACK', 'ROLLED_BACK'],
                # "nsComponentTypes": ['VNF', 'NS', 'PNF'],
                # "lcmOpNameImpactingNsComponent": ['VNF_INSTANTIATE', 'VNF_SCALE', 'VNF_SCALE_TO_LEVEL',
                #                                  'VNF_CHANGE_FLAVOUR', 'VNF_TERMINATE', 'VNF_HEAL', 'VNF_OPERATE',
                #                                  'VNF_CHANGE_EXT_CONN', 'VNF_MODIFY_INFO', 'NS_INSTANTIATE',
                #                                  'NS_SCALE', 'NS_UPDATE', 'NS_TERMINATE', 'NS_HEAL'],
                # "lcmOpOccStatusImpactingNsComponent": ['START', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED',
                #                                       'ROLLED_BACK']
            },
            "CallbackUri": callback_uri,
        }
        response = self.post_x(data, "/nslcm/v1/subscriptions")
        logger.info(response.text)
        if check_rest_response(response):
            return True
        return False

    # def execute_primitive(self, ns_id: str, vnf_index: int, primitive_name: str, param_key: str, param_value: str) -> dict:
    def execute_primitive(self, ns_id: str, pdata: dict) -> dict:
        if 'member_vnf_index' in pdata and type(pdata['member_vnf_index']) is not str:
            pdata['member_vnf_index'] = str(pdata['member_vnf_index'])

        response = self.post_x(pdata, "/nslcm/v1/ns_instances/{}/action".format(ns_id))
        logger.debug("execute_primitive response= " + str(response.json()))
        if check_rest_response(response):
            operation_res = self.wait_for_operation("ns", response.json()['id'], 3600)
            return {
                "response": response.text,
                "details": operation_res['details'],
                "status": response.status_code,
                "charm_status": "completed" if operation_res['success'] is True else "failed"
            }
        else:
            return {"response": response.text, "status": response.status_code, "charm_status": "failed"}

    def wait_for_operation(self, ns_nsi: str, opp_id: str, timeout: int) -> dict:
        if ns_nsi == "ns":
            url = "/nslcm/v1/ns_lcm_op_occs/{}".format(opp_id)
        elif ns_nsi == "nsi":
            url = "/nsilcm/v1/nsi_lcm_op_occs/{}".format(opp_id)
        else:
            raise ValueError('wait_for_operation: first parameter must be ns or nsi, not ' + ns_nsi)
        wait = timeout
        while wait >= 0:
            r = self.get_x(url)
            if not check_rest_response(r):
                return {'success': False, 'details': r.reason}
            nslcmop = r.json()
            # logger.debug("wait_for_operation r= " + r.text)
            if ("COMPLETED" in nslcmop["operationState"]) or ("completed" in nslcmop["operationState"]):
                logger.info("INFO - Operation {} successfully completed".format(opp_id))
                return {'success': True, 'details': nslcmop}
            elif ("FAILED" in nslcmop["operationState"]) or ("failed" in nslcmop["operationState"]):
                logger.error("ERROR - Operation {} failed".format(opp_id))
                return {'success': False, 'details': nslcmop}
            wait -= 10
            time.sleep(10)
        logger.error("ERROR - NS operation {} has not finished after {} seconds".format(opp_id, timeout))
        return {'success': False, 'details': 'nfvcl timeout expired'}

    # Physical Deployment Units ###############################################################################
    def get_pdu_list(self) -> dict:
        r = self.get_x("/pdu/v1/pdu_descriptors")
        if check_rest_response(r):
            return r.json()
        else:
            raise ValueError("PDU list not found!")

    def get_pdu_detail(self, id_: str) -> dict:
        r = self.get_x("/pdu/v1/pdu_descriptors/{1}".format(self.osm_nbi_url, id_))
        if check_rest_response(r):
            return r.json()
        else:
            logger.error("PDU {} not found!".format(id_))
            return {}

    def delete_pdu(self, id_: str):
        result = self.delete_x('/pdu/v1/pdu_descriptors/' + str(id_))
        # logger.debug(result)
        if check_rest_response(result):
            return True
        else:
            logger.error('PDU deletion error')
            logger.error(result.reason)
            return False

    def add_pdu(self, data: dict):
        result = self.post_x(data, '/pdu/v1/pdu_descriptors')
        # logger.debug(result)
        if check_rest_response(result):
            return result.json()
        else:
            logger.error('PDU creation error')
            logger.error(result.reason)
            logger.warning(result.text)
            return False

    # Kubernetes Clusters ###################################################################################
    def add_k8s_cluster_model(self, vim: str, k8s_cluster: K8sModel):
        return self.add_k8s_cluster(name=k8s_cluster.name,
                             conf=k8s_cluster.credentials,
                             k8s_version=k8s_cluster.k8s_version,
                             vim=vim,
                             k8s_net_names=k8s_cluster.networks)


    def add_k8s_cluster(self, name: str, conf: str, k8s_version: str, vim: str, k8s_net_names: List[str]):
        if len(self.get_k8s_clusters()) > 0:
            logger.warning('trying to onboard multiple k8s clusters. OSM currently support one cluster. Aborting')
            return False
        k8s_nets = {}
        for net_name in k8s_net_names:
            k8s_nets[net_name] = net_name

        data = {
            "name": name,
            "credentials": yaml.safe_load(conf),
            "vim_account": vim,
            "k8s_version": k8s_version,
            "deployment_methods": {
                "helm-chart": False,
                "helm-chart-v3": True,
                "juju-bundle": False
            },
            "nets": k8s_nets
        }
        result = self.post_x(data, '/admin/v1/k8sclusters')
        if check_rest_response(result):
            logger.debug("Successfully onboarded K8s cluster ->{}<-".format(name))
            return result.json()
        else:
            logger.error('error on k8s cluster creation')
            logger.error(result)
            logger.error(result.text)
            return False

    def get_k8s_clusters(self, cluster_name: str = ""):
        """
        Retrieve the k8s cluster from OSM, given the cluster name (NOT the id!)

        @param cluster_name: the name of the cluster to retrieve

        @return the k8s cluster (in osm) in JSON format, False if not found
        #todo use pydantic model for K8s info from osm
        """
        url = "/admin/v1/k8sclusters"
        if cluster_name != "":
            url += "/?name={}".format(cluster_name)
        r: requests.Response = self.get_x(url)
        # logger.debug("{} --- {}".format(r.status_code, r.text))
        if check_rest_response(r):
            return r.json()
        else:
            return False

    def get_k8s_cluster_id(self, name=None):
        """
        Filter the k8s cluster id from the JSON info about a k8s retrieved from OSM

        @param name the name of the cluster to search. If null, the method looks for the id of all k8s clusters present.

        @return the id of the first match
        """
        res_json = self.get_k8s_clusters(cluster_name=name)
        return next((item['_id'] for item in res_json if item['name'] == name), None)

    def check_k8s_cluster_onboarded(self) -> bool:
        """
        Check if there is at least one k8s cluster onboarded on OSM.
        Returns:
            True if present, false otherwise.
        """
        res_json = self.get_k8s_clusters()
        if res_json==False:
            return False
        else:
            return True


    def delete_k8s_cluster(self, name: str):
        """
        Delete a k8s from OSM

        @param name: the name of the cluster to delete (different from id)

        @return response in json format if it is deleted, False otherwise
        """
        repo_id = self.get_k8s_cluster_id(name)
        result = self.delete_x('/admin/v1/k8sclusters/{}'.format(repo_id))
        # logger.debug(result)
        if check_rest_response(result):
            return result.json()
        else:
            logger.error("k8s repository creation error: {}".format(result.reason))
            return False

    # Virtual Infrastructure Managers ########################################################################
    def add_vim(self, data):
        result = self.post_x(data, '/admin/v1/vim_accounts')
        # logger.debug(result)
        if check_rest_response(result):
            return result.json()
        else:
            logger.error("VIM creation error: {}".format(result.reason))
            return False

    def del_vim(self, vim_id):
        result = self.delete_x('/admin/v1/vim_accounts/' + str(vim_id))
        if check_rest_response(result):
            return result.json()
        else:
            logger.error("VIM deletion error: {}".format(result.reason))
            return False

    def get_vims(self):
        r = self.get_x("/admin/v1/vims/")
        if check_rest_response(r):
            return r.json()
        else:
            raise ValueError("VIM list cannot be retrieved")

    def get_vim_by_tenant_and_name(self, name: str, tenant: str):
        r = self.get_x("/admin/v1/vims/?vim_tenant_name={}&name={}".format(tenant, name))
        if check_rest_response(r):
            vim_list = r.json()
            if vim_list is None or not vim_list:
                msg_err = 'VIM >{}< not found on OSM with tenant name >{}<'.format(name, tenant)
                logger.error(msg_err)
                raise ValueError(msg_err)
            else:
                return vim_list[0]
        else:
            return None

    # Repositories ######################################################################################
    def add_k8s_repo(self, name: str, url: str):
        """
        Add a K8s helm repo to OSM. It is then possible to use custom helm chart, present in the repo, on OSM.
        Args:
            name: The name to be given at the chart repo, will be used to indicate helm chart in the repo
                  (example name=nfvcl-repo, chart=free5gc -> nfvcl-repo/free5gc).
                  Must be composed only by lower case letters, numbers and minus (-)
            url: The url of the helm repo
        """
        # Checking that the name of the repo added to OSM is composed only by lower case letters, numbers and -.
        # Otherwise, the charts are not found by OSM
        if not bool(match("[a-z0-9\-]*$", name)):
            msg_err = "The name of the K8s helm repo is not formatted correctly. oOnly lower case letters, numbers and -"
            logger.error(msg_err)
            raise ValueError
        data = {
            "name": name,
            "description": "{} chart repository".format(name),
            "type": "helm-chart",
            "url": url
        }
        result = self.post_x(data, '/admin/v1/k8srepos')
        if check_rest_response(result):
            return result.json()
        else:
            logger.error("k8s repository creation error: {}".format(result.reason))
            return False

    def get_k8s_repos(self):
        r = self.get_x("/admin/v1/k8srepos")
        if check_rest_response(r):
            res = r.json()
            return res
        else:
            return False

    def delete_k8s_repo(self, name: str):
        repo = next((item for item in self.get_k8s_repos() if item['name'] == name), None)
        if repo is None:
            logger.warning('Helm repository with name {} not existing'.format(name))
            return False

        result = self.delete_x('/admin/v1/k8srepos/{}'.format(repo['_id']))
        # logger.debug('delete_k8s_repo - delete_x result: {}'.format(result))
        if check_rest_response(result):
            return result.json()
        else:
            logger.error("K8s repository creation error: {}".format(result.reason))
            return False

    def get_kdu_services(self, nsi, kdu_name):
        vnfi_list = self.get_vnfi_list(nsi)
        for v in vnfi_list:
            vnf_detail = self.get_vnfi_detail(v['id'])
            if 'kdur' in vnf_detail:
                for k in vnf_detail['kdur']:
                    if k['kdu-name'] == kdu_name:
                        return k['services']
        raise ValueError('kdur {} not found'.format(kdu_name))


nbi_util_instance: NbiUtil = None


def get_osm_nbi_utils() -> NbiUtil:
    global nbi_util_instance
    """
    Utils created to avoid importing all the parameters into subclasses.
    """
    if not nbi_util_instance:
        nfvcl_config = get_nfvcl_config()
        nbi_util_instance = NbiUtil(username=nfvcl_config.osm.username, password=nfvcl_config.osm.password,
                   project=nfvcl_config.osm.project, osm_ip=nfvcl_config.osm.host, osm_port=nfvcl_config.osm.port)
    return nbi_util_instance
