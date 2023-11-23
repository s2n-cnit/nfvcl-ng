# Getting started

After installing NFVCL with the instruction provided in this repository's `README.md` follow the instruction in

- [Topology creation](topology/topology_creation.md)

to add an OpenStack server as VIM.

Before proceeding with the following instructions you need to upload Ubuntu cloud images to the VIMs, images need to be named as follow:
* ubuntu2204
* ubuntu2004
* ubuntu1804

To avoid uploading manually images you can use the dedicated API `/v1/openstack/update_images`, it asks Openstack to download these images (⚠️ It takes several minutes).

The current version of NFVCL can deploy the following blueprints:

