BLUE_GET_PODS_DESCRIPTION: str = "Returns a list of pods belonging to the specified blueprint. The returned dict is" \
                                 "obtained from parsing kubernetes.client->V1PodList into dict. This call return a empty" \
                                 "list if that blueprint has no associated k8s pods. The returned pods are taken from" \
                                 "the namespace that name correspond with blue ID"

BLUE_GET_PODS_SUMMARY: str = "Returns a list of pods belonging to blueprint"