BLUE_GET_PODS_DESCRIPTION: str = "Returns a list of pods belonging to the specified blueprint. The returned dict is" \
                                 "obtained from parsing kubernetes.client->V1PodList into dict. This call return a " \
                                 "empty list if that blueprint has no associated k8s pods. The returned pods are taken"\
                                 " from the namespace that name correspond with blue ID"

BLUE_GET_PODS_SUMMARY: str = "Returns a list of pods belonging to blueprint"

ADD_EXTERNAL_K8SCLUSTER: str = "Add a k8s cluster, not generated from a blueprint or generated from a blueprint but" \
                               " not present to the topology, to the topology"
ADD_EXTERNAL_K8SCLUSTER_SUMMARY: str = "Add a external k8s cluster to the topology"

ADD_K8SCLUSTER_DESCRIPTION: str = "Add a k8s cluster, generated from a blueprint, to the topology. The blueprint id" \
                                  " is mandatory"
ADD_K8SCLUSTER_SUMMARY: str = "Add a blueprint generated k8s cluster to the topology"

UPD_K8SCLUSTER_DESCRIPTION: str = "Update a K8s cluster, already present in the topology, with the new given data"
UPD_K8SCLUSTER_SUMMARY: str = "Update NFVCL k8s cluster"

ADD_PROM_SRV_DESCRIPTION: str = "Add Prometheus server instance to the topology. This will be used to collect data from" \
                                "node exporters added from the NFVCL. Jobs to pull data from node exporters will be" \
                                "added to the prom server."
ADD_PROM_SRV_SUMMARY: str = "Add Prometheus server to be used by NFVCL."

UPD_PROM_SRV_DESCRIPTION: str = "Update Prometheus server instance in the topology. This will be used to collect data" \
                                " from node exporters added from the NFVCL. Jobs to pull data from node exporters will" \
                                " be added to the prom server."
UPD_PROM_SRV_SUMMARY: str = "Update Prometheus server to be used by NFVCL."

DEL_PROM_SRV_DESCRIPTION: str = "Delete Prometheus server instance from the topology."
DEL_PROM_SRV_SUMMARY: str = "Delete Prometheus instance from the topology."

GET_PROM_SRV_DESCRIPTION: str = "Retrieve a specific Prometheus server instance from the topology, given the ID of" \
                                "the instance."
GET_PROM_SRV_SUMMARY: str = "Retrieve a specific Prometheus server instance"

GET_PROM_LIST_SRV_DESCRIPTION: str = "Retrieve the list of Prometheus server instances from the topology"
GET_PROM_LIST_SRV_SUMMARY: str = "Retrieve the list of Prometheus server instances"
