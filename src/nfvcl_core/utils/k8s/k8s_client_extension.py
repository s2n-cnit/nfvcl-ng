import logging
import os
from json import JSONDecodeError
import kubernetes
import yaml
from kubernetes.client import ApiException, ApiClient
from kubernetes.utils import create_from_dict, FailToCreateError
from nfvcl_core.utils.log import create_logger

logger: logging.Logger = create_logger("K8S CLIENT EXTENSION")

handled_custom_api = ["metallb.io/v1beta1", "operator.tigera.io/v1", "cert-manager.io/v1"]

"""
This extension to k8s is necessary when using Custom Resources Definitions (CRDs).
A more clean way to solve this problem is probably to generate a new client, adding CRDs to API schema.
For this moment this will be used as solution.
"""


def skip_if_already_exists(failure_list, failure, existing_resources: int = 0) -> int:
    """
    This method avoid the execution to block when adding an existing resource to a k8s cluster.
    It avoids to throw Exceptions.
    When a Failure that is NOT an 'alreadyExist' problem happens it will be added to the failure list.

    Args:
        failure_list: the list to be populated with different Exceptions/Failures different from 'alreadyExist'
        failure: The Failure to be analyzed.
        existing_resources: a counter. It is incremented if failure is 'alreadyExist'. Default value 0.

    Returns:
        The counter or the incremented counter, depending on the type of failure.
    """
    import json
    # Found in https://github.com/kubernetes-client/python/blob/master/kubernetes/utils/create_from_yaml.py#L165
    try:
        if hasattr(failure, 'api_exceptions'):
            # FailToCreateError
            info = json.loads(failure.api_exceptions[0].body)
        else:
            # ApiException
            info = json.loads(failure.body)

        if info.get('reason').lower() == 'alreadyexists':
            print(failure)
            return existing_resources + 1
        else:
            # Adding the failure to the list and the returning the counter NOT incremented.
            failure_list.append(failure)
            return existing_resources
    except JSONDecodeError as error:
        print(failure)
        return existing_resources


def create_from_yaml_custom(
        k8s_client,
        yaml_file=None,
        yaml_objects=None,
        verbose=False,
        namespace="default",
        **kwargs):
    """
    Extension of kubernetes.utils.create_from_yaml. See its documentation for further details.
    This extension allow to create custom resources, not provided by the k8s client.
    In this case only operator.tigera.io (CRD) is supported.
    """

    def create_with(objects):
        """
        Inner function
        """
        failures = []
        k8s_objects = []
        # Counter of existing resources
        existing_resources: int = 0
        for yml_document in objects:
            if yml_document is None:
                continue
            try:
                api_ver: str = yml_document['apiVersion']
                if api_ver in handled_custom_api:
                    # If CRD of type operator.tigera.io/v1 calling custom method
                    created = create_custom_resource(k8s_client, yml_document)
                else:
                    # Otherwise call the default function from the library
                    created = create_from_dict(k8s_client, yml_document, verbose,
                                               namespace=namespace,
                                               **kwargs)
                # Appending the created res
                k8s_objects.append(created)
            except FailToCreateError as failure:
                existing_resources = skip_if_already_exists(failures, failure, existing_resources)
            except ApiException as failure:
                existing_resources = skip_if_already_exists(failures, failure, existing_resources)
        if existing_resources > 0:
            logger.warning("During yaml application {} resources were already existing.".format(existing_resources))
        if failures:
            # If failures different from already exist resources throw error.
            raise FailToCreateError(failures)
        return k8s_objects

    if yaml_objects:
        # If yaml content is passed to this method
        yml_document_all = yaml_objects
        return create_with(yml_document_all)
    elif yaml_file:
        # Otherwise if yaml file is passed to this method
        with open(os.path.abspath(yaml_file)) as f:
            yml_document_all = yaml.safe_load_all(f)
            return create_with(yml_document_all)
    else:
        raise ValueError('One of `yaml_file` or `yaml_objects` arguments must be provided')


def create_custom_resource(k8s_client: ApiClient, yml_document):
    """
    Function to support Custom Resources Definitions (CDRs). Otherwise the official k8s client for python will fail
    when trying to apply a yaml containing these resources.

    Args:
        k8s_client: The k8s client, already configured.
        yml_document: the yaml definition to be applied at the cluster, containing the custom resources.

    Returns:
        # TODO check return type
    """
    api_name: str = yml_document['apiVersion']
    # api_ver is like 'operator.tigera.io/v1' or 'v1' in case of core api
    api_ver_splitted = api_name.split('/')
    # Accepting only apiname/vx.c.z format
    if len(api_ver_splitted)<=1:
        raise ValueError("Type of api not supported {}: must have a / inside, like ->operator.tigera.io/v1-<")
    else:
        api_grp = api_ver_splitted[0]
        api_version = api_ver_splitted[1]
    api_kind: str = yml_document['kind']
    plural = api_kind.lower() + 's'
    custom_api_client = kubernetes.client.CustomObjectsApi(k8s_client)

    # TODO: if the namespace is present in the yaml but the resource doesn't support it, it will fail.
    # In kubectl the yaml is applied anyway, but the namespace is ignored.
    if 'namespace' in yml_document['metadata']:
        namespace = yml_document['metadata']['namespace']
        created = custom_api_client.create_namespaced_custom_object(group=api_grp, version=api_version,
                                                                    namespace=namespace, plural=plural,
                                                                    body=yml_document)
    else:
        created = custom_api_client.create_cluster_custom_object(group=api_grp, version=api_version,
                                                                 plural=plural, body=yml_document)
    return created
