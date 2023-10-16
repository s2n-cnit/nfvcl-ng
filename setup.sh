#!/bin/bash
echo "Adding MongoDB GPG keys..."
curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/mongodb-6.gpg
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

echo "Adding Python 3.11 repo"
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

echo "Installing python3.11"
sudo apt install python3.11

echo "Installing Poetry"
curl -sSL https://install.python-poetry.org | python3 -

echo "install uvicorn..."
sudo apt install -y uvicorn

echo "install redis-server..."
sudo apt install -y redis-server
sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
echo "Restarting redis..."
sudo systemctl restart redis

echo "Installing python3.11..."
sudo apt install python3.11
sudo apt install python3.11-dev

echo "Install MongoDB..."
sudo apt install -y mongodb-org
sudo systemctl enable --now mongod

echo "configure mongodb..."
sudo sed -i '/bindIp/ s/127\.0\.0\.1/0\.0\.0\.0/' /etc/mongod.conf
echo "Restarting mongodb..."
sudo systemctl restart mongodb

echo "Fixing PodSecurity issue for VNFM"
kubectl set env deployment -n osm lcm OSMLCM_VCA_EEGRPC_POD_ADMISSION_POLICY=privileged

echo "Setting up the registry for local image deployment"
docker run -d -p 5000:5000 --restart=always --name registry registry:2
echo "Building VNFM image"
# The build should take enough time to let the registry start
docker build -t localhost:5000/vnfm-ee ./vnf_managers/helmflexvnfm --no-cache
docker push localhost:5000/vnfm-ee
