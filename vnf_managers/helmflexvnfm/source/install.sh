#!/bin/bash
##
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
##
echo "installing ansible"
#
#apt-get install -y ...
apt update
#
printf "\n INSTALL ANSIBLE DEPEND - install -y software-properties-common python3-pip wget"
apt install -y software-properties-common python3-pip wget
printf "\n ADDING EXTERNAL ANSIBLE REPO"
apt-add-repository --yes --update ppa:ansible/ansible
printf "\n UPDATING REPOS"
apt update
printf "\n INSTALLING ANSIBLE"
apt install -y ansible
#
# Set host checking to false
echo "host_key_checking = False" >> /etc/ansible/ansible.cfg
#
echo "UPGRADING PIP"
/usr/bin/python3 -m pip install --upgrade pip
printf "\n INSTALLING PyYAML, requests, paramiko"
pip3 install PyYAML
pip3 install requests
pip3 install paramiko
#
printf "\nINSTALLING ANSIBLE COLLECTION FOR VYOS and JINJA dependency\n"
pip3 install jinja2
ansible-galaxy collection install vyos.vyos
#
#curl -s https://storage.googleapis.com/golang/go1.17.1.linux-amd64.tar.gz | tar -v -C /usr/local -xz
#export PATH=$PATH:/usr/local/go/bin
#export GOPATH=/go
#
#go get github.com/go-logfmt/logfmt && go get github.com/go-kit/kit/log
#
#wget -q https://github.com/prometheus/snmp_exporter/archive/v0.20.0.tar.gz -P /tmp/ \
#&& tar -C /tmp -xf /tmp/v0.20.0.tar.gz \
#&& (cd /tmp/snmp_exporter-0.20.0/generator && go build) \
#&& cp /tmp/snmp_exporter-0.20.0/generator/generator /usr/local/bin/snmp_generator
#
#
#