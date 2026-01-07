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
- Install uvicorn, uv, Redis and MongoDB.
- Configure Redis to listen from all interfaces
- Install dependencies using uv
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
> :warning: It may be necessary to use the absolute path '/home/ubuntu/.local/bin/uv' for running the NFVCL.
``` 
screen -S nfvcl
uv run python -m nfvcl_rest
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
ExecStart=/home/ubuntu/.local/bin/uv run python -m nfvcl_rest

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

To see the logs of the service run:

`journalctl -u nfvcl`

### Log file
The file can be found in the logs folder of NFVCL, it's called `nfvcl.log`. 
It is a rotating log with 4 backup files that are rotated when the main one reach 50Kbytes.
In case of NFVCL **crash** it is the only place where you can observe it's output.
