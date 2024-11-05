<a name="readme-top"></a>

# 🐎 HORSE Section 
You can find APIs examples in [Horse test section](/src/nfvcl/rest_endpoints/HORSE/api_examples)

The file containing APIs for HORSE is [there](src/nfvcl/rest_endpoints/HORSE/horse.py)

<!-- TABLE OF CONTENTS -->

# 📗 Table of Contents

- [📖 About the Project](#-nfvcl)
  - [Key Features](#key-features)
- [💻 Getting Started](#-getting-started)
  - [Setup](#setup)
  - [Requirements](#requirements)
  - [Setup](#setup)
  - [Install](#install)
  - [Configuration](#configuration)
  - [Running🏃](#running-)
  - [Deployment🎈 (Docker+Helm)](#deployment)
  - [Usage📖](#usage-)
  - [Debug🧪](#debug-)
- [👥 Authors](#-authors)
- [🤝 Contributing](#-contributing)
- [⭐️ Show your support](#-show-your-support)
- [📝 License](#-license)

<!-- PROJECT DESCRIPTION -->

# 📖 NFVCL

The NFVCL is a network-oriented meta-orchestrator, specifically designed for zeroOps and continuous automation. 
It can create, deploy and manage the lifecycle of different network ecosystems by consistently coordinating multiple 
artefacts at any programmability levels (from physical devices to cloud-native microservices).
A more detailed description of the NFVCL will be added to the [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html).

![General scheme](docs/images/NVFCL-diagrams-General-Scheme.drawio.svg)

## Key Features

- **Deploy Blueprints that build 5G, Kubernetes, VyOS .... services**
- **Manage the lifecicle of Blueprints**
- **Manage K8S cluster and Machines/VMs**

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Technology used

* Ansible: Configuring deployed VMs
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

## 💻 Getting Started
To run the NFVCL you have several possible alternatives:
 1. [RECOMMENDED] Use the provided docker compose (skip to [Deployment](#deployment) part)
 2. Use the provided helm chart
 3. Install requirements and run on your machine (follow next instructions)

To get a local copy up and running (point 2), follow these steps.

### Requirements

1. The NFVCL can run on:
   - A Kubernetes (K8S) cluster, the installation using Helm is available [here](#helm-installation-kubernetes)
   - Docker engine using the Docker compose file on the GitHub repository[1] or using the NFVCL container image (in the second case MongoDB and Redis must have been installed and configured separately)
   - A (Virtual) Machine using Ubuntu 22.04 LTS (In future 24 LTS), using the instructions provided on the GitHub README[1]. MongoDB and Redis, working and configured, are needed. 

2. Performance requirements: The NFVCL is not a software that requires high performance, for a virtual machine is more than enough 2VCPUs, 4GB of RAM and 15GB of disk. The requirements inside Docker and K8S still have to be evaluated.

3. Deploy requirements: The NFVCL at the moment is supporting 2 types of Hypervisors on which it can work: OpenStack and Proxmox. At least one hypervisor, and access to it, is needed by the NFVCL to deploy Blueprints. To fully automate the deployment process a full access to the hypervisor is required, if this is not the case some operations may fail due to insufficient permissions (image creations, disable port security…)

4. Network access to Internet or at least to images.tnt-lab.unige.it and registry.tnt-lab.unige.it to download VM and Container images required by Blueprints

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

### Configuration
The last step is the NFVCL configuration, it can be done though the configuration file or using [ENV variables](config/config.md).
In production, it is suggested to change values in `config/config.yaml`, while, for developing you can create a copy of the default configuration and call it `config/config_dev.yaml`. 
When the NFVCL starts, it loads the configuration from `config/config_dev.yaml` if present, otherwise the configuration is loaded from the default file.

> [!TIP]
> The IP of the NFVCL is not mandatory, use it to bind on a specific interface.
> Redis **IP** should be 127.0.0.1 if they are running on the same machine of NFVCL.

```
{
  'log_level': 20, # 10 = DEBUG, CRITICAL = 50,FATAL = CRITICAL, ERROR = 40, WARNING = 30, WARN = WARNING, INFO = 20, DEBUG = 10, NOTSET = 0
  'nfvcl': {
    'version': "0.2.1",
    'port': 5002,
    'ip': '' # CAN BE LEFT EMPTY
  },
  'osm': {
    'host': '127.0.0.1',
    'port': '9999',
    'username':'admin',
    'password':'admin',
    'project': 'admin',
    'version': 12
  },
  'mongodb': {
    'host': '127.0.0.1',
    'port': 27017,
    'db': 'nfvcl'
  },
  'redis': {
    'host': '127.0.0.1',
    'port': 6379
  }
}
```


### Running 🏃
You can use `screen` or create a service to run the NFVCL in the background

#### Using Screen
Once configuration is done you can run the NFVCL in the background using **screen**.
> :warning: It may be necessary to use the absolute path '/home/ubuntu/.local/bin/poetry' for running the NFVCL.
``` 
screen -S nfvcl
poetry run python -m nfvcl
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

### Deployment🎈
You can deploy this project using **Docker** or **Helm** (Kubernetes)

- [Docker](https://nfvcl-ng.readthedocs.io/en/latest/docker.html)
- [Helm installation (Kubernetes)](https://nfvcl-ng.readthedocs.io/en/latest/helm.html)

### Usage 📖
The NFVCL usage is described in the dedicated [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html) page.

### Debug 🧪
The NFVCL main output is contained in the **console output**, but additionally it is possible to observe it's output in log files and 
published on Redis events.

##### Screen
Resume the console using `screen -r`

##### Service
`journalctl -u nfvcl`

##### Log file
The file can be found in the logs folder of NFVCL, it's called nfvcl.log. 
It is a rotating log with 4 backup files that are rotated when the main one reach 50Kbytes.
In case of NFVCL **crash** it is the only place where you can observe it's output.

##### Redis **NFVCL_LOG** topic
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
The NFVCL development is supported by the [5G-INDUCE](https://www.5g-induce.eu/) project 

<!-- SUPPORT -->

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## ⭐️ Show your support

If you like this project hit the star button!

<!-- LICENSE -->

## 📝 License

This project is [GPL3](./LICENSE) licensed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
