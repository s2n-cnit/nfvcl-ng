#!/bin/bash
set -e
echo "Adding MongoDB GPG keys..."
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/8.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list


echo "Adding Python 3.12 and ansible repo"
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-add-repository --yes --update ppa:ansible/ansible
sudo apt update

echo "Installing python3.12"
sudo apt install -y python3.12 python3.12-dev python3.12-venv pipx

pipx ensurepath

echo "Installing Ansible"
sudo apt install -y ansible
sudo mkdir -p /etc/ansible
sudo touch /etc/ansible/ansible.cfg
if grep -q 'host_key_checking = False' /etc/ansible/ansible.cfg; then
    echo "Skipping ansible cfg since it already exist"
else
    echo -e '[defaults]\nhost_key_checking = False' | sudo tee -a /etc/ansible/ansible.cfg
fi


echo "Installing Helm"
sudo apt-get install apt-transport-https --yes
curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
echo echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update
sudo apt-get install helm

echo "Installing uv"
pipx install uv

echo "install uvicorn..."
sudo apt install -y uvicorn

echo "install redis-server..."
sudo apt install -y redis-server
sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
echo "Restarting redis..."
sudo systemctl restart redis

echo "Install MongoDB..."
sudo apt install -y mongodb-org
sudo systemctl enable --now mongod

echo "configure mongodb..."
sudo sed -i '/bindIp/ s/127\.0\.0\.1/0\.0\.0\.0/' /etc/mongod.conf
echo "Restarting mongod..."
sudo systemctl restart mongod

# Needed by some python packages (netifaces)
echo "Installing build essential tools"
sudo apt install -y build-essential sshpass

echo "Installing Python project dependencies"
/home/ubuntu/.local/bin/uv sync

echo "Installing Ansible Collections"
ansible-galaxy collection install vyos.vyos
ansible-galaxy collection install prometheus.prometheus
ansible-galaxy collection install git+https://github.com/s2n-cnit/nfvcl-ansible-collection.git,v0.0.1
