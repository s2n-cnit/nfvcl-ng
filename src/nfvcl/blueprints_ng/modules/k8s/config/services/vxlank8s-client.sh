#!/bin/bash
ip link add vxlan-{{ vx_name }} type vxlan id {{ vxid }} remote {{ vx_server_floating_ip if vx_server_floating_ip is not none else vx_server_ip}} local {{ vx_client_ip }} dev CLIENT_DEV dstport {{ vx_server_ext_port }}
ip addr add {{ vxlan_client_int_ip }} dev vxlan-{{ vx_name }}
ip link set up dev vxlan-{{ vx_name }}
