<a name="readme-top"></a>

<!-- TABLE OF CONTENTS -->

# 📗 Table of Contents

- [📖 About the Project](#-nfvcl)
  - [Key Features](#key-features)
- [💻 Getting Started](#-getting-started)
  - [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Install](#install)
  - [Usage](#usage)
  - [Deployment](#deployment)
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

![General scheme](https://raw.githubusercontent.com/s2n-cnit/nfvcl-ng/master/docs/images/NVFCL-diagrams-General-Scheme.drawio.svg)

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

> [!IMPORTANT]  
> If you are using the provided docker compose, skip to [Usage](#usage) part.

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


### Usage

You can use `screen` or create a service to run the NFVCL in the background

#### Using Screen
Once configuration is done you can run the NFVCL in the background using **screen**.
> :warning: It may be necessary to use the absolute path '/home/ubuntu/.local/bin/poetry' for running the NFVCL.
``` 
screen -S nfvcl
poetry run python ./run.py
```
> :warning: To deatach from screen press **CTRL+a** then **d**.
> To resume the screen run `screen -r nfvcl`.

#### Create a service
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
ExecStart=/home/ubuntu/.local/bin/poetry run python /home/ubuntu/nfvcl-ng/run.py

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

### Deployment

You can deploy this project using Doker or Kubernetes

#### Docker
![Docker compose scheme](https://raw.githubusercontent.com/s2n-cnit/nfvcl-ng/master/docs/images/NVFCL-diagrams-DockerCompose.drawio.svg)

Clone the repo:
``` bash
git clone --depth 1 https://github.com/s2n-cnit/nfvcl-ng
```
Then run docker compose
``` bash
docker compose up
```

#### Kubernetes
Still to be implemented

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
