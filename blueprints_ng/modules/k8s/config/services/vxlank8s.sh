#!/bin/bash
ip link add vxlan-{{ vx_name }} type vxlan id {{ vxid }} remote {{ vx_client_ip }} local {{ vx_server_ip }} dev {{ vx_server_ext_device }} dstport {{ vx_server_ext_port }}
ip addr add {{ vxlan_server_int_ip }}/24 dev vxlan-{{ vx_name }}
ip link set up dev vxlan-{{ vx_name }}
