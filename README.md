<a name="readme-top"></a>

# 🐎 HORSE Section 
You can find APIs examples in [Horse test section](/src/nfvcl/rest_endpoints/HORSE/api_examples)

The file containing APIs for HORSE is [there](src/nfvcl/rest_endpoints/HORSE/horse.py)

<!-- TABLE OF CONTENTS -->

# 📗 Table of Contents

<!-- TOC -->
* [📗 Table of Contents](#-table-of-contents)
* [:book: NFVCL](#book-nfvcl)
  * [:boom: Key Features](#boom-key-features)
    * [:wrench: Technology used](#wrench-technology-used)
  * [:whale2: Getting Started - Docker](#whale2-getting-started---docker)
    * [Docker Compose files](#docker-compose-files)
  * [:anchor: Getting Started - K8s](#anchor-getting-started---k8s)
  * [Getting Started - Local](#getting-started---local)
    * [Requirements](#requirements)
    * [Setup](#setup)
    * [Install](#install)
    * [Configuration - Local](#configuration---local)
    * [Running 🏃](#running-)
      * [Using Screen](#using-screen)
      * [Using a service](#using-a-service)
  * [Configuration](#configuration)
  * [Usage 📖](#usage-)
  * [Debug 🧪](#debug-)
    * [Screen](#screen)
    * [Service](#service)
    * [Log file](#log-file)
    * [Redis **NFVCL_LOG** topic](#redis-nfvcl_log-topic)
  * [👥 Authors](#-authors)
    * [Original Authors](#original-authors)
    * [Mantainers](#mantainers)
    * [Contributors](#contributors)
  * [🤝 Contributing](#-contributing)
  * [💸 Fundings](#-fundings)
  * [⭐️ Show your support](#-show-your-support)
  * [📝 License](#-license)
<!-- TOC -->

<!-- PROJECT DESCRIPTION -->

# :book: NFVCL

The NFVCL is a network-oriented meta-orchestrator, specifically designed for zeroOps and continuous automation. 
It can create, deploy and manage the lifecycle of different network ecosystems by consistently coordinating multiple 
artefacts at any programmability levels (from physical devices to cloud-native microservices).
A more detailed description of the NFVCL will be added to the [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html).

![General scheme](docs/images/NVFCL-diagrams-General-Scheme.drawio.svg)

## :boom: Key Features

- **NFVCL** has Blueprints that:
    - Deploy and manage 5G Cores (Free5GC, OAI, SDCore, ...)
        - Creation/Deletion of a core over a K8S cluster
        - Add/Remove Slices
        - Add/Remove DNNs
        - Add/Remove TACs
        - Possibility to choose the UPF type
        - Automatic gNB configuration (Physical and Virtual)
    - Deploy and manage Kubernetes Clusters 
        - Creation/Deletion of a K8S cluster over one or more VIMs (Openstack, Proxmox)
        - Add/Remove Nodes
        - Automatic installation of plugins (Calico, Flannel, MetalLB, OpenEBS)
    - Deploy virtual routers (VyOS)
        - Creation/Deletion of a VyOS routers over one or more VIMs (Openstack, Proxmox)
        - Add/Remove NAT rules
    - Deploy Ubuntu VMs
        - Creation/Deletion of Ubuntu VMs over one or more VIMs (Openstack, Proxmox)
    - Deploy UERANSIM
        - Creation/Deletion of UERANSIM gNB and UEs
        - Automatic configuration of UERANSIM devices gNBs
        - Desired number of UEs for each VM


- **Manage K8S cluster onboarded in the NFVCL Topology**
    - Add/Remove Namespaces, Pods, ...
    - Apply yaml definition
    - Creates certificates for new users with granted permissions over specific namespaces.
    - ...

> :information_source: Some operations may sound as simple as creating a VM, but the NFVCL is designed to automate these operations such that time is
saved and the process can be repeated to reproduce multiple times the same environment.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### :wrench: Technology used

* Ansible: Information gathering and configuration of deployed VMs
* Helm: Creating all the required K8S resources in a cluster
* K8S APIs: Installing plugins on deployed or existing clusters, retrieving information, appling resource definition from yaml
* Openstack APIs: Creating, connecting and initialising VMs. Creating dedicated networks for the operation of some type of Blueprints
* Proxmox APIs: used to create, connect and initialise VMs on Proxmox
* SSH: accessing and upload files on Proxmox hypervisors, required to apply Ansible playbooks on remote VMs
* Poetry: managing the Python dependencies
* Redis: used to send log and events
* MongoDB: storing all the permanent data required to track Blueprints

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## :whale2: Getting Started - Docker

To launch the application using Docker Compose, you need to have Docker and Docker Compose installed on your machine. If you don't have them installed, you can follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/).

Once you have Docker and Docker Compose installed, you can run the following command to launch the application:

> **Warning:** You should choose the appropriate Docker Compose file based on your requirements. See the [Docker Compose files](#docker-compose-files) section for more information.

> **Warning:** You might use `docker-compose` instead of `docker compose` depending on your Docker Compose version.

To start the application (after [Configuration](#configuration)), run the following command:
```bash
git clone https://github.com/s2n-cnit/nfvcl-ng.git
# OPTIONAL change to the desired branch
cd nfvcl-ng
cd docker-compose
docker compose -f compose.yaml up -d
```
To stop the application, run the following command:
```bash
docker compose -f compose.yaml down
```

### Docker Compose files
- The `stable` one (`compose-stable.yaml`), updated less frequently but should not include unstable features.
- The `master` (`compose.yaml`) is updated as soon as a cycle of improvements has been made and partially tested
- The `latest` (`compose-latest.yaml`) branch is the one updated as soon as new features/fix are implemented. 
- The `latest` (`compose-dev.yaml`) It is the branch used for development.
- The `build` (`compose-build.yaml`) is the one used to build the application locally on the branch you have downloaded.


## :anchor: Getting Started - K8s
[Helm installation (Kubernetes)](https://nfvcl-ng.readthedocs.io/en/latest/helm.html)

## Getting Started - Local

### Requirements
1. A (Virtual) Machine using Ubuntu 24.04 LTS. MongoDB and Redis, working and configured, are needed. 

2. Performance requirements: The NFVCL is not a software that requires high performance, for a VM is more than enough 2VCPUs, 4GB of RAM and 15GB of disk. The requirements inside Docker and K8S still have to be evaluated.

3. Deploy requirements: The NFVCL at the moment is supporting 2 types of Hypervisors on which it can work: **OpenStack** and **Proxmox**. At least one hypervisor, and access to it, is needed by the NFVCL to deploy Blueprints. To fully automate the deployment process a full access to the hypervisor is required, if this is not the case some operations may fail due to insufficient permissions (image creations, disable port security…)

4. Network **access** to Internet or at least to **images.tnt-lab.unige.it** and **registry.tnt-lab.unige.it** to download VM and Container images required by Blueprints

5. Network access to deployed VMs and to K8S clusters to configure resources deployed using Blueprints.
<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Setup

The first step to run the software locally is to clone the repository. We have 3 main different branches:
- The `stable` one, updated less frequently but should not include unstable features.
- The `master` is updated as soon as a cycle of improvements has been made and partially tested
- The `dev` branch is the one updated as soon as new features/fix are implemented. It is the branch used for development.

Clone the desired branch to your desired folder:
``` bash
git clone https://github.com/s2n-cnit/nfvcl-ng
git switch stable
```

### Install

Enter NFVCL folder and run setup.sh, this script will:
- Install uvicorn, Poetry, Redis and MongoDB.
- Configure Redis to listen from all interfaces
- Install dependencies using Poetry
``` 
cd nfvcl-ng
chmod +x ./setup.sh
./setup.sh
```

### Configuration - Local
See the [Configuration](#configuration) section for more information.

### Running 🏃
You can use `screen` or create a service to run the NFVCL in the background

#### Using Screen
Once configuration is done you can run the NFVCL in the background using **screen**.
> :warning: It may be necessary to use the absolute path '/home/ubuntu/.local/bin/poetry' for running the NFVCL.
``` 
screen -S nfvcl
poetry run python src/nfvcl_rest/__main__.py
```
> :warning: To detach from screen press **CTRL+a** then **d**.
> To resume the screen run `screen -r nfvcl`.

#### Using a service
Create a service file: `sudo nano /etc/systemd/system/nfvcl.service` with the following content
>:warning: Change the values in case you performed a custom installation
```
[Unit]
Description=Example service
After=network.target
StartLimitIntervalSec=0

[Service]
WorkingDirectory=/home/ubuntu/nfvcl-ng
Type=simple
Restart=always
RestartSec=10
User=ubuntu
ExecStart=/home/ubuntu/.local/bin/poetry run python /home/ubuntu/nfvcl-ng/src/nfvcl/__main__.py

[Install]
WantedBy=multi-user.target
```
```
sudo systemctl daemon-reload
sudo systemctl start nfvcl.service
```
Check the status of the service and, in case it's everything ok, enable the service.
```
sudo systemctl status nfvcl.service
sudo systemctl enable nfvcl.service
```

## Configuration
NFVCL configuration can be done though the configuration file or using [ENV variables](config/config.md).
In production, it is suggested to change values in `config/config.yaml`, while, for developing you can create a copy of the default configuration and call it `config/config_dev.yaml`. 
When the NFVCL starts, it loads the configuration from `config/config_dev.yaml` if present, otherwise the configuration is loaded from the default file.


> :information_source: Redis and Mongo **IP** should be 127.0.0.1 if they are running on the same machine of NFVCL.

> :warning: Authentication is disabled by default, to enable it set `authentication: True` in the configuration file.
> Default user is `admin` and the password is `admin`

```
---
log_level: "20" # 20 is info, 10 is debug
nfvcl:
  port: "5002"
  ip: "0.0.0.0" # Listen on every interface
  authentication: False
mongodb:
  host: "127.0.0.1"
  port: "27017"
  db: "nfvcl"
#  username: "admin"
#  password: "password"
redis:
  host: "127.0.0.1"
  port: "6379"
```


## Usage 📖
The NFVCL usage is described in the dedicated [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html) page.

## Debug 🧪
The NFVCL main output is contained in the **console output**, but additionally it is possible to observe it's output in log files and 
published on Redis events.

### Screen
Resume the console using `screen -r`

### Service
`journalctl -u nfvcl`

### Log file
The file can be found in the logs folder of NFVCL, it's called `nfvcl.log`. 
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

## 👥 Authors
### Original Authors

👤 **Roberto Bruschi**

- GitHub: [@robertobru](https://github.com/robertobru)

### Mantainers
👤 **Paolo Bono**

- GitHub: [@PaoloB98](https://github.com/PaoloB98)
- LinkedIn: [Paolo Bono](https://www.linkedin.com/in/paolo-bono-2576a3132/)

👤 **Alderico Gallo**

- GitHub: [@AldericoGallo](https://github.com/AldericoGallo)

👤 **Davide Freggiaro**

- GitHub: [@DavideFreggiaro](https://github.com/DavideFreggiaro)

### Contributors
👤 **Guerino Lamanna**

- GitHub: [@guerol](https://github.com/guerol)

👤 **Alireza Mohammadpour**

- GitHub: [@AlirezaMohammadpour85](https://github.com/AlirezaMohammadpour85)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

Feel free to check the [issues page](../../issues/).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## 💸 Fundings
The NFVCL development has been supported by the [5G-INDUCE](https://www.5g-induce.eu/) project 

<!-- SUPPORT -->

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## ⭐️ Show your support

If you like this project hit the star button!

<!-- LICENSE -->

## 📝 License

This project is [GPL3](./LICENSE) licensed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
