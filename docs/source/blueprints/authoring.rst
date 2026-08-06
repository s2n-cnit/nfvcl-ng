====================
Blueprint authoring
====================

This guide shows the implementation patterns used by the built-in blueprints.
Use the generated :doc:`../api/source/nfvcl_models` and
:doc:`../api/source/nfvcl_core_models` references for request and resource
models, and :doc:`../api/source/nfvcl_providers` for provider methods.

Blueprint structure
===================

New blueprints normally inherit from ``BlueprintNG[State, CreateModel]``. The
state is a Pydantic model derived from ``BlueprintNGState`` and stores the
resources needed to reload and continue the instance. The creation model is a
Pydantic model used by the REST endpoint.

The usual lifecycle is:

1. Call ``super().create(create_model)``.
2. Construct resources and configurators.
3. Register each object with ``self.register_resource(...)``.
4. Execute the provider operations in the required order.
5. Expose Day-2 operations with ``@day2_function``.

Do not put deployment work in ``__init__``: blueprints are reconstructed from
the database and the constructor can run more than once.

Kubernetes blueprint
====================

The reference implementation is
``nfvcl.blueprints_ng.modules.k8s.k8s_blueprint.K8sBlueprint``. It creates a
master and worker ``VmResource`` objects, registers them, and uses the
``VmK8sDay0Configurator`` for initial cluster installation. Later operations
use the Day-2 and Day-N configurators. A simplified flow is:

.. code-block:: python

   @blueprint_type("example-k8s")
   class ExampleK8sBlueprint(BlueprintNG[ExampleState, K8sCreateModel]):
       def create(self, model: K8sCreateModel):
           super().create(model)
           master = VmResource(...)
           self.register_resource(master)
           self.provider.create_vm(master)

           configurator = VmK8sDay0Configurator(...)
           self.register_resource(configurator)
           self.provider.configure_vm(configurator)
           self.provider.topology_manager.add_kubernetes(...)

       @day2_function("/add_worker", [HttpRequestType.POST])
       def add_worker(self, model: AddNodeModel):
           ...

The actual request fields, node placement, flavors, CIDRs, and topology
onboarding rules are defined by ``K8sCreateModel`` and documented in the
existing :doc:`k8s/k8s_blue_creation` examples.

VM and Ubuntu configuration
============================

``nfvcl.blueprints_ng.modules.ubuntu.ubuntu_blueprint.UbuntuBlueprint`` is the
smallest complete VM example. It creates a ``VmResource`` with a
``VmResourceImage`` and ``VmResourceFlavor``, registers it, calls
``provider.create_vm``, then registers a ``VmUbuntuConfigurator`` for Day-2
configuration:

.. code-block:: python

   self.state.vm = VmResource(
       area=model.area,
       name=f"{self.id}_VM",
       image=VmResourceImage(name="ubuntu", url=model.image_url),
       flavor=model.flavor,
       username="ubuntu",
       password=model.password,
       management_network=model.mgmt_net,
       additional_networks=model.data_nets,
   )
   self.register_resource(self.state.vm)
   self.provider.create_vm(self.state.vm)

   self.state.configurator = VmUbuntuConfigurator(vm_resource=self.state.vm)
   self.register_resource(self.state.configurator)

   @day2_function("/apt_install", [HttpRequestType.PUT])
   def apt_install(self, model: UbuntuInstallAptModel):
       self.state.configurator.install_apt_packages(model.packages)
       self.provider.configure_vm(self.state.configurator)

The attached Simulaqron blueprint follows this same VM pattern, with a fixed
image and a ``SimulaqronCreateModel`` containing ``area``, ``password``,
``mgmt_net``, ``data_nets``, and ``flavor``.

PNF/PDU configuration
=====================

For a physical or simulated network function, use the PDU provider and a
PDU configurator. PacketRusher is the existing VM-backed example in
``nfvcl.blueprints_ng.modules.packetrusher.packetrusher_blue``. A typical flow
is:

.. code-block:: python

   pdu = PduModel(...)
   self.register_resource(pdu)
   self.provider.add_pdu(pdu)

   configurator = GNBPDUConfigurator(...)
   self.register_resource(configurator)
   self.provider.configure_pdu(configurator)

Concrete configurators such as ``AmariPDUConfigurator`` implement
``configure``, ``detach``, and (where supported) ``configure_ric`` by building
Ansible tasks. Keep playbook construction in ``dump_playbook`` and keep the
blueprint responsible for lifecycle ordering and request validation.

Day-2 endpoints
===============

Decorate each public operation with its URL suffix and allowed HTTP methods.
The blueprint manager supplies the blueprint ID as part of the endpoint
context; request paths and complete payloads should be verified against the
running Swagger UI at ``http://NFVCL-IP:5002/docs``.

Before registering a new resource, ensure its provider is available in the
topology. VM resources require a VIM; Helm and Kubernetes operations require a
Kubernetes provider; PDU operations require the corresponding PDU support.