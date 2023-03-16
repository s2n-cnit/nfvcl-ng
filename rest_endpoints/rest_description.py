BLUE_GET_PODS_DESCRIPTION: str = "Returns a list of pods belonging to the specified blueprint. The returned dict is" \
                                 "obtained from parsing kubernetes.client->V1PodList into dict. This call return a empty" \
                                 "list if that blueprint has no associated k8s pods. The returned pods are taken from" \
                                 "the namespace that name correspond with blue ID"

BLUE_GET_PODS_SUMMARY: str = "Returns a list of pods belonging to blueprint"

ADD_EXTERNAL_K8SCLUSTER: str = "Add a k8s cluster, not generated from a blueprint or generated from a blueprint but not present to the topology, to the topology"
ADD_EXTERNAL_K8SCLUSTER_SUMMARY: str = "Add a external k8s cluster to the topology"

ADD_K8SCLUSTER_DESCRIPTION: str = "Add a k8s cluster, generated from a blueprint, to the topology. The blueprint id is mandatory"
ADD_K8SCLUSTER_SUMMARY: str = "Add a blueprint generated k8s cluster to the topology"
