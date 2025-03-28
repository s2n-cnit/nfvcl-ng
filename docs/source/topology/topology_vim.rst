====================
Topology VIM setup
====================

After a VIM has been added to the Topology it could be **not** ready to be used. You must check internet connectivity from VMs,
create networks required for Blueprints creation (see :doc:`blueprints/blueprint') and check if there are resources avaiable in the tenant space.

With the NEW Blueprint system it is NO more required to upload manually the images on the VIM. The NFVCL, when deploying a VM,
will give to the VIM the URL where the image can be downloaded.

The URL of the image can be external (like for Ubuntu base images) or offered by the us through the https://images.tnt-lab.unige.it/ service.

.. warning::
    The https://images.tnt-lab.unige.it/ service needs to be reachable from the VIM.

.. image:: ../../images/NVFCL-diagrams-NFVCL_VIM_interaction.drawio.svg
  :width: 400
  :alt: Alternative text
