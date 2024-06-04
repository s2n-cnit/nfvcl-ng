#!/bin/bash
ip link add eth99 type dummy
# IP address for the machine
ip addr add {{ vm_ipaddress }}/24 dev eth99
# Ip addresses for the load balancer
{% for ipaddress in pool_ipaddresses %}
ip addr add {{ ipaddress }}/24 dev eth99
{% endfor %}
ip link set dev eth99 up
