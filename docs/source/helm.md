# Helm

This section is dedicated to the installation of the NFVCL in a Kubernetes cluster using [Helm](https://helm.sh/).

The deployment on kubernetes will have this structure:

```{image} ../images/NVFCL-diagrams-Helm-Chart.drawio.svg
:alt: Select Parameters
:width: 400px
:align: center
```

## Requirements

- A K8S cluster with Load Balancer installed and with an ipaddresspool (in auto assign mode) enabled
- Helm installed and configured on a machine (with target the cluster of the previous point)
- Clone the NFVCL locally using git

## Installation
Get inside the folder of helm template
```shell
cd nfvcl-ng/helm-nfvcl
```
Install the chart (helm install DEPLOYNAME .)
```shell
ubuntu@atzbpy-vm-k8s-c:~/nfvcl-ng/helm-nfvcl$ helm install test .
NAME: test
LAST DEPLOYED: Fri Jun 21 08:43:12 2024
NAMESPACE: default
STATUS: deployed
REVISION: 1
NOTES:
```
Wait till PODS are running
```shell
ubuntu@atzbpy-vm-k8s-c:~/nfvcl-ng/helm-nfvcl$ kubectl get pods -n nfvcl-test
NAME                                READY   STATUS    RESTARTS   AGE
mongo-deployment-7459cc7c7c-lzcl5   1/1     Running   0          3m3s
nfvcl-deployment-78db5c986d-4n6mg   1/1     Running   0          3m3s
redis-deployment-5c5648fbf4-ztsgs   1/1     Running   0          3m3s
```

Check the services
```shell
ubuntu@atzbpy-vm-k8s-c:~/nfvcl-ng/helm-nfvcl$ kubectl get svc -n nfvcl-test
NAME        TYPE           CLUSTER-IP       EXTERNAL-IP      PORT(S)           AGE
mongo-svc   NodePort       10.200.107.4     <none>           27017:31000/TCP   3m32s
nfvcl-svc   LoadBalancer   10.200.116.135   10.255.255.102   5002:30965/TCP    3m32s
redis-svc   NodePort       10.200.224.76    <none>           6379:32000/TCP    3m32s
```

You can see that the NFVCL is exposed using a `LoadBalancer`, while for debug, mongo and redis are exposed using `NodePort`.

In this case, the swagger can be accessed on [http://10.255.255.102:5002](http://10.255.255.102:5002) and on node port `30965` (for all nodes). APIs are exposed in both cases.

Instead, MondoDB and Redis can be accessed on `31000` and `32000` (for all nodes). If you want you can change the service type of
Mongo and Redis to [ClusterIP](https://kubernetes.io/docs/concepts/services-networking/service/#type-clusterip) to make it impossible 
to access from the outside.

## Logs
Logs can be accessed using kubectl as follows
```shell
ubuntu@atzbpy-vm-k8s-c:~/nfvcl-ng/helm-nfvcl$ kubectl get pods -n nfvcl-test
NAME                                READY   STATUS    RESTARTS   AGE
mongo-deployment-7459cc7c7c-lzcl5   1/1     Running   0          16m
nfvcl-deployment-78db5c986d-4n6mg   1/1     Running   0          16m
redis-deployment-5c5648fbf4-ztsgs   1/1     Running   0          16m
ubuntu@atzbpy-vm-k8s-c:~/nfvcl-ng/helm-nfvcl$ kubectl logs -n nfvcl-test nfvcl-deployment-78db5c986d-4n6mg
Defaulted container "nfvcl" out of: nfvcl, init-wait-for-redis (init)
The currently activated Python version 3.10.12 is not supported by the project (^3.11).
Trying to find and use a compatible version.
Using python3.11 (3.11.9)
2024-06-21 10:43:30 [Main                ][MainThread] [    INFO] [SYSTEM] Starting subscribers
2024-06-21 10:43:30 [Topology Worker     ][Thread-1 (] [   DEBUG] [SYSTEM] Started listening
Applying migration migration_001_initial
...
```
