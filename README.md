<a name="readme-top"></a>

<p style="text-align: center;">
  <img src="/docs/images/logo/logo.png" alt="Description" width="200" height="200">
</p>

<!-- TABLE OF CONTENTS -->

# 📗 Table of Contents

<!-- TOC -->
* [📗 Table of Contents](#-table-of-contents)
* [:book: NFVCL](#book-nfvcl)
  * [:boom: Key Features](#boom-key-features)
    * [:wrench: Technology used](#wrench-technology-used)
  * [:whale2: Getting Started - Docker](#whale2-getting-started---docker)
  * [:anchor: Getting Started - K8s](#anchor-getting-started---k8s)
  * [Local execution](#local-execution)
  * [Configuration](#configuration)
  * [Usage 📖](#usage-)
  * [Debug 🧪](#debug-)
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
* uv: managing the Python dependencies
* Redis: used to send log and events
* MongoDB: storing all the permanent data required to track Blueprints

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## :whale2: Getting Started - Docker

[Docker documentation](https://nfvcl-ng.readthedocs.io/en/latest/docker.html)

## :anchor: Getting Started - K8s
[Helm installation (Kubernetes)](https://nfvcl-ng.readthedocs.io/en/latest/helm.html)

## Local execution
[Running with Python](https://nfvcl-ng.readthedocs.io/en/latest/local.html)

## Configuration
[Configuration Docs](https://nfvcl-ng.readthedocs.io/en/latest/conf.html)

## Usage 📖
The NFVCL usage is described in the dedicated [Wiki](https://nfvcl-ng.readthedocs.io/en/latest/index.html) page.

## Debug 🧪
The NFVCL main output is contained in the **console output**, but additionally it is possible to observe it's output in log files.

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
