#!/bin/bash

echo "install uvicorn..."
sudo apt install -y uvicorn

echo "install redis-server..."
sudo apt install -y redis-server

echo "install mongodb..."
sudo apt install -y mongodb

echo "configure mongodb..."
sudo sed -i '/bind_ip/ s/127\.0\.0\.1/0\.0\.0\.0/' /etc/mongodb.conf
sudo systemctl restart mongodb

echo "restart mongodb..."
sudo service restart mongodb

echo "create directories..."
mkdir -p "helm_charts/charts/"
mkdir "day2_files"
