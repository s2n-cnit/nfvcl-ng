<a name="readme-top"></a>

<!-- TABLE OF CONTENTS -->

# 📗 Table of Contents

- [📖 About the Project](#-nfvcl)
  - [Key Features](#key-features)
- [💻 Getting Started](#-getting-started)
  - [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Install](#install)
  - [Running](#running)
  - [Deployment](#deployment)
  - [Usage](#usage)
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
- **Manage the lifecicle of blueprints**
- **Manage K8S cluster and Machines/VMs**

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## 💻 Getting Started
To run the NFVCL you have several possible alternatives:
 1. [RECOMMENDED] Use the provided docker compose (skip to [Deployment](#deployment) part)
 2. Install requirements and run on your machine (follow next instructions)
 3. Use the provided helm chart (STILL TO BE UPLOADED)

To get a local copy up and running (point 2), follow these steps.

### Prerequisites

 - An OpenStack instance (you can use all-in-one installation [here](https://docs.openstack.org/devstack/rocky/guides/single-machine.html))
 - An Ubuntu (22.04 LTS) instance where the NFVCL will be installed and run.
 - Having OSM 14 running on a reachable machine, in the following installation procedure,
   all the services will be installed on the same Ubuntu instance.
 - Python 3.11 (Installation performed in setup.sh)
 - If the NFVCL and OSM are running on the same machine:
   - **RECOMMENDED**: 
          4 CPUs, 16 GB RAM, 80GB disk and a single interface with Internet access
   - **MINIMUM**: 
          2 CPUs, 8 GB RAM, 50GB disk and a single interface with Internet access
### Setup
> [!WARNING]  
> The instruction for OSM installation is not anymore provided from this project.

Clone this repository to your desired folder:
``` bash
git clone --depth 1 https://github.com/s2n-cnit/nfvcl-ng
```


### Install

Enter NFVCL folder and run setup.sh, this script will:
- Install uvicorn, Poetry, Redis and MongoDB.
- Configure Redis to listen from all interfaces
- Fix PodSecurity for VNFM
- Setting up a local Docker registry
- Build and upload the VNFM image to local registry
- Install dependencies using Poetry
``` 
cd nfvcl-ng
chmod +x ./setup.sh
./setup.sh
```

### Configuration
The last step is the NFVCL configuration. 
In production it is raccomanded to change values in **config.yaml**, while, for developing you can create a copy of the default configuration and call it **config_dev.yaml**. 
When the NFVCL starts, it loads the cofiguration from *config_dev.yaml* if present, otherwise the configuration is loaded from the default file.

> [!TIP]
> The IP of the NFVCL is not mandatory, use it to bind on a specific interface.
> OSM and Redis **IPs** sould be 127.0.0.1 if they are running on the same machine of NFVCL.

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


### Running

You can use `screen` or create a service to run the NFVCL in the background

#### Using Screen
Once configuration is done you can run the NFVCL in the background using **screen**.
> :warning: It may be necessary to use the absolute path '/home/ubuntu/.local/bin/poetry' for running the NFVCL.
``` 
screen -S nfvcl
poetry run python -m nfvcl
```
> :warning: To deatach from screen press **CTRL+a** then **d**.
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

#### Debug
The NFVCL main output is contained in the **console output**, but additionally it is possible to observe it's output in:
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

### Deployment

You can deploy this project using Doker or Kubernetes

#### Docker
![Docker compose scheme](docs/images/NVFCL-diagrams-DockerCompose.drawio.svg)

Clone the repo:
``` bash
git clone --depth 1 https://github.com/s2n-cnit/nfvcl-ng
```
Then run docker compose
``` bash
docker compose up
```
For the Docker container, to visualize logs it is sufficient to use `docker logs` utility.

#### Kubernetes
Still to be implemented

### Usage
The NFVCL usage is described in the dedicated [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html) page.

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

<!-- SUPPORT -->

## ⭐️ Show your support

If you like this project hit the star button!

<!-- LICENSE -->

## 📝 License

This project is [GPL3](./LICENSE) licensed.
