#!/bin/bash

echo "install uvicorn..."
sudo apt install -y uvicorn

echo "install redis-server..."
sudo apt install -y redis-server
sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' /etc/redis/redis.conf
echo "Restarting redis..."
sudo systemctl restart redis

echo "install mongodb..."
sudo apt install -y mongodb

echo "configure mongodb..."
sudo sed -i '/bind_ip/ s/127\.0\.0\.1/0\.0\.0\.0/' /etc/mongodb.conf
echo "Restarting mongodb..."
sudo systemctl restart mongodb



echo "create directories..."
mkdir -p "helm_charts/charts/"
mkdir -p "day2_files"
mkdir -p "logs"

echo "Building VNFM image"

docker build -t vnfm_ee ./vnf_managers/helmflexvnfm --no-cache