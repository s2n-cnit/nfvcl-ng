# NFVCL-NG
The NFVCL is a network-oriented meta-orchestrator, specifically designed for zeroOps and continuous automation. 
It can create, deploy and manage the lifecycle of different network ecosystems by consistently coordinating multiple 
artefacts at any programmability levels (from physical devices to cloud-native microservices).
A more detailed description of the NFVCL will be added to the [Wiki](https://github.com/s2n-cnit/nfvcl-ng/wiki).

<!-- TOC -->
* [NFVCL-NG](#nfvcl-ng)
  * [External Architecture](#external-architecture)
  * [Requirements](#requirements)
  * [Installation](#installation)
    * [Step 0 - Cloning and downloading required files/dependencies](#step-0---cloning-and-downloading-required-filesdependencies)
    * [Step 1 - Install OSM](#step-1---install-osm)
    * [Step 2 - Install Redis, Uvicorn, MongoDB and requirements](#step-2---install-redis-uvicorn-mongodb-and-requirements)
    * [Step 3 - Configure NFVCL, Redis and MongoDB](#step-3---configure-nfvcl-redis-and-mongodb)
  * [Run and Test NFVCL](#run-and-test-nfvcl)
<!-- TOC -->

## External Architecture

![alt text](https://raw.githubusercontent.com/s2n-cnit/nfvcl-ng/master/docs/images/nfvcl-Context.svg)

Usually we install NFVCL, Redis, MongoDB and OSM on the same machine, but throght configuration it is possible to locate these services as you desire.
In this guide they will be installed on the same location.

## Requirements
 - An OpenStack instance (you can use all-in-one installation [here](https://docs.openstack.org/devstack/rocky/guides/single-machine.html))
 - An Ubuntu (22.04 LTS) instance where the NFVCL will be installed and run.
 - Having OSM 14 running on a reachable machine, in the following installation procedure,
   all the services will be installed on the same Ubuntu instance.
 - Python 3.11.
 - **RECOMMENDED**: 
		4 CPUs, 16 GB RAM, 80GB disk and a single interface with Internet access
 - **MINIMUM**: 
		2 CPUs, 8 GB RAM, 50GB disk and a single interface with Internet access

## Installation
On the Ubuntu 22.04 instance perform the following steps.
### Step 0 - Cloning and downloading required files/dependencies
1. Download OSM 14
``` bash
wget https://osm-download.etsi.org/ftp/osm-14.0-fourteen/install_osm.sh
```
2. Download NFVCL software
``` bash
git clone --depth 1 https://github.com/s2n-cnit/nfvcl-ng
```
### Step 1 - Install OSM

The OSM installation is automatic, it's sufficient to run a shell script. It takes a lot of time, **more than 20 minutes**.
1. Start osm installation
``` bash
chmod +x install_osm.sh
./install_osm.sh
```
From OSM 14 on, we will need to execute also the following instruction
``` bash
kubectl set env deployment -n osm lcm OSMLCM_VCA_EEGRPC_POD_ADMISSION_POLICY=privileged
```

### Step 2 - Install Redis, Uvicorn, MongoDB and requirements

Enter NFVCL folder and run setup.sh, this script will:
- Install uvicorn, Poetry, Redis and MongoDB.
- Configure Redis to listen from all interfaces
- Fix PodSecurity for VNFM
- Setting up a local Docker registry
- Build and upload the VNFM image to local registry
- Install dependencies using Poetry
``` 
cd nfvcl-ng-private
chmod +x ./setup.sh
./setup.sh
```

### Step 3 - Configure NFVCL, Redis and MongoDB
The last step is the NFVCL configuration, in production it is raccomanded to change values in **config.yaml**, while, for developing you can create a copy of the default configuration and call it **config_dev.yaml**. When the NFVCL starts, it loads the cofiguration from *config_dev.yaml* if present, otherwise the configuration is loaded from the default file.


The NFVCL's **IP** must concide with the one of the machine on witch it is installed and running.
OSM and Redis **IPs** sould be 127.0.0.1 if they are running on the same machine of NFVCL.


## Run and Test NFVCL
Once configuration is done you can run the NFVCL in the background using **screen**.
``` 
screen -S nfvcl
poetry run python ./run.py
```
> :warning: To deatach from screen press **CTRL+a** then **d**.
> To resume the screen run `screen -r nfvcl`.

## Usage
To interact with the NFVCL you must use REST APIs, a full list is available at:
`http://NFVCL_IP:5002/docs`

> :warning: Before you begin you will need to define the topology using the appropriate APIs.

You can find request examples in the [wiki](https://github.com/s2n-cnit/nfvcl-ng/wiki)


## Debug
The NFVCL main output is contained in the **console output**, but additionally it is possible to observe it's output in:
### Log file
The file can be found in the logs folder of NFVCL, it's called nfvcl.log. 
It is a rotating log with 4 backup files that are rotated when the main one reach 50Kbytes.
In case of NFVCL **crash** it is the only place where you can observe it's output.

### Redis **NFVCL_LOG** topic
You can attach on the Redis pub-sub system to subscribe at the NFVCL log, the topic that must be observed is **NFVCL_LOG**.
This is useful when you don't have access to the console output.
In order to attach at the NFVCL output it is required to have the Redis IP and port.


You can use the following Python script as example:

> :warning: **Change the IP and Redis port!!!**

```python
import redis

redis_instance = redis.Redis(host='192.168.X.X', port=XYZC, db=0)

redis_pub_sub = redis_instance.pubsub()

redis_pub_sub.subscribe("NFVCL_LOG")
redis_pub_sub.subscribe("TOPOLOGY")

for message in redis_pub_sub.listen():
    # When you subscribe to a topic a message is returned from redis to indicate if the
    # subscription have succeeded.
    # The confirmation message['data'] contains a 'int' while NFVCL output contains 'bytes'
    if isinstance(message['data'], bytes):
        print(message['data'].decode())
    else:
        print(message['data'])
```

## Report Issues
Report issues [Here](https://github.com/s2n-cnit/nfvcl-ng/issues) and provide:
- What API call has been called
- The URL and body of the request
- The Topology status
- The output of the NFVCL (can be obtained through Redis)
- The status of related resources on OpenStack
- If needed, any optional info and a description of what you were doing.
