#!/bin/bash
echo "Adding MongoDB GPG keys..."
curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/mongodb-6.gpg
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

echo "Adding Python 3.11 and ansible repo"
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-add-repository --yes --update ppa:ansible/ansible
sudo apt update

echo "Installing python3.11"
sudo apt install -y python3.11 python3.11-dev python3.11-venv python3.11-distutils

echo "Installing Ansible"
sudo apt install -y ansible
sudo mkdir /etc/ansible
sudo touch /etc/ansible/ansible.cfg
echo -e '[defaults]\nhost_key_checking = False' | sudo tee -a /etc/ansible/ansible.cfg

echo "Installing Poetry"
curl -sSL https://install.python-poetry.org | python3 -

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
/home/ubuntu/.local/bin/poetry install

echo "Installing Ansible Collections"
sudo ansible-galaxy collection install vyos.vyos
sudo ansible-galaxy collection install prometheus.prometheus
sudo ansible-galaxy collection install git+https://github.com/s2n-cnit/nfvcl-ansible-collection.git,v0.0.1
