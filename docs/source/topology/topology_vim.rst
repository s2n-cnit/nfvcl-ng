====================
Topology VIM setup
====================

After a VIM as been added to the Topology it could happen that it is still not possible to use it.

This happens using the OLD Blueprint system where VM's images should be uploaded on the VIM before it can be used.

With the NEW Blueprint system it is NO more required to upload manually the images on the VIM. The NFVCL, when deploying a VM,
will give to the VIM the URL where the image can be downloaded.

The URL of the image can be external (like for Ubuntu base images) or offered by the us through the http://images.tnt-lab.unige.it/ service.

.. warning::
    The http://images.tnt-lab.unige.it/ service needs to be reachable from the VIM.

.. image:: ../../images/NVFCL-diagrams-NFVCL_VIM_interaction.drawio.svg
  :width: 400
  :alt: Alternative text

.. list-table:: Images to be uploaded in VIM if using OLD Blueprint version
   :widths: 25 25 50
   :header-rows: 1

   * - Image name
     - Image
     - Used by blueprint
   * - ubuntu2204
     - Ubuntu 22.04 LTS
     - K8s (v1)
   * - vyos
     - VyOS (see build :doc:`/blueprints/vyos/vyos_blue_creation`)
     - VyOS (v1)
   * - ...
     - ...
     - ...

For **Ubuntu** images you can use the API at (POST - /v1/openstack/update_images) to automatically **download/update**
Ubuntu images, it takes several minutes.

