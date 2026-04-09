from ipaddress import IPv4Network
from typing import Optional

import json5
from pydantic import BaseModel, Field

from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNGState
from nfvcl_core_models.custom_types import NFVCLCoreException
from nfvcl_core_models.resources import VmResourceAnsibleConfiguration

from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder, ServiceState
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_models.blueprint_ng.amarisoft.core import QoSFlow, PDNConfig, PdnSlice, SNSSAI
from nfvcl_models.blueprint_ng.g5.custom_types_5g import sd_to_int

MME_FILE_NAME = "mme.cfg"
UE_DB_FILE_NAME = "ue_db-ims.cfg"


def to_serializable(obj):
    """
    Recursively converts Pydantic models and lists to plain Python dicts/lists
    so that json5 can serialise them.

    ``QoSFlow`` is handled first because it requires alias-based serialisation
    (the field names in the JSON output differ from the Python attribute names).

    Args:
        obj: A QoSFlow, any other BaseModel subclass, a list, or a scalar.

    Returns:
        A JSON-serialisable representation of ``obj``.
    """
    if isinstance(obj, QoSFlow):
        return obj.model_dump(by_alias=True)
    if isinstance(obj, BaseModel):
        return {k: to_serializable(v) for k, v in obj.__iter__()}
    if isinstance(obj, list):
        return [to_serializable(i) for i in obj]
    return obj


class AmarisoftInstallator(VmResourceAnsibleConfiguration):
    """
    Ansible configurator that downloads and installs the Amarisoft software
    on the core VM.

    The playbook fetches the tarball from an internal mirror, extracts it,
    and runs the vendor install script with the appropriate feature flags
    (MME, NAT, no IMS, etc.).
    """

    amarisoft_tar_url: str = "127.0.0.1"
    download_path: Optional[str] = "/root/amarisoft.tar.gz"
    extract_path: Optional[str] = "/root"
    install_dir: Optional[str] = "2026-03-13"
    """Name of the subdirectory produced by extraction (used to locate the install script)."""

    def dump_playbook(self) -> str:
        """
        Builds and returns the Ansible playbook that installs Amarisoft.

        Variables injected into the playbook:

        - ``amarisoft_url`` — Full URL of the Amarisoft tarball.
        - ``download_path`` — Destination path for the downloaded tarball.
        - ``extract_path``  — Directory where the tarball will be extracted.
        - ``install_dir``   — Subdirectory name used to locate the install script.
        """
        ansible_builder = AnsiblePlaybookBuilder("Playbook Amari Core Installation")
        ansible_builder.set_var("amarisoft_url", self.amarisoft_tar_url)
        ansible_builder.set_var("download_path", self.download_path)
        ansible_builder.set_var("extract_path", self.extract_path)
        ansible_builder.set_var("install_dir", self.install_dir)
        ansible_builder.add_tasks_from_file(rel_path("config/playbooks/amari_core_install.yaml"))
        return ansible_builder.build()


class AmarisoftConfigurator(VmResourceAnsibleConfiguration):
    """
    Ansible configurator that applies the running configuration to the
    Amarisoft core VM.

    On each invocation (day-0 and every day-2 operation) the playbook:

    1. Regenerates the UE database (``ue_db-ims.cfg``) from the current subscriber list.
    2. Regenerates the MME configuration (``mme.cfg``) from the current slices and DNNs.
    3. Deploys the ``start.sh`` / ``stop.sh`` route scripts and the ``routes``
       systemd service that manages IP routing for GTP traffic.

    All configuration is re-generated from scratch on every run; there is no
    incremental diff. This keeps the logic simple and idempotent.
    """

    amarisoft_5g_state: Generic5GBlueprintNGState
    """Full 5G state snapshot; read-only — used only to extract configuration data."""

    gpt_bind_address: str
    """IP address of the core VM's N3 interface, used as the GTP bind address in mme.cfg."""

    license_server_addr: str = "127.0.0.1"
    """IP address of the Amarisoft licence server."""

    config_dest_path: str = "/root/mme/config"
    """Remote directory where MME and UE-DB configuration files will be placed."""

    gnb_cidr: Optional[str] = Field(default=None)
    """CIDR of the gNB network, injected into start.sh as the destination for gNB-bound routes."""

    n3_gateway: Optional[str] = Field(default=None)
    """IP of the router's N3 interface; used as the next-hop for gNB-bound traffic in start.sh."""

    n6_gateway: Optional[str] = Field(default=None)
    """IP of the router's N6 interface; used as the default gateway for UE traffic in start.sh."""

    def dump_playbook(self) -> str:
        """
        Builds and returns the Ansible playbook that configures the Amarisoft core.

        The playbook is assembled in three logical sections:

        1. UE database — subscriber credentials rendered into ``ue_db-ims.cfg``.
        2. MME config  — PDN/slice data rendered into ``mme.cfg``.
        3. Routes      — ``start.sh``, ``stop.sh``, and ``routes.service`` deployed
                         and the systemd service started.
        """
        ansible_builder = AnsiblePlaybookBuilder("Playbook Amari Core Configurator")

        # Global vars shared across all templates in this playbook
        ansible_builder.set_var("gpt_addr", self.gpt_bind_address)
        ansible_builder.set_var("plmn", self.amarisoft_5g_state.current_config.config.plmn)
        ansible_builder.set_var("license_server_addr", self.license_server_addr)

        self._add_ue_db_tasks(ansible_builder)
        self._add_mme_tasks(ansible_builder)
        self._add_route_tasks(ansible_builder)

        return ansible_builder.build()

    # -------------------------------------------------------------------------
    # dump_playbook helpers
    # -------------------------------------------------------------------------

    def _add_ue_db_tasks(self, ansible_builder: AnsiblePlaybookBuilder):
        """
        Injects the subscriber list variable and adds the UE-database template
        rendering task to the playbook.

        Each subscriber entry carries the IMSI, authentication key (K), and
        operator code (OPC) required by the Amarisoft UE DB template.

        Args:
            ansible_builder: The playbook builder to append tasks to.
        """
        subscribers_data = [
            {"imsi": s.imsi, "k": s.k, "opc": s.opc}
            for s in self.amarisoft_5g_state.current_config.config.subscribers
        ]
        ansible_builder.set_var("subscribers", subscribers_data)
        ansible_builder.add_template_task(
            rel_path("config/ue_db-ims.cfg.jinja2"),
            f"{self.config_dest_path}/{UE_DB_FILE_NAME}"
        )

    def _add_mme_tasks(self, ansible_builder: AnsiblePlaybookBuilder):
        """
        Builds the PDN and AMF-slice lists, injects them as variables, and adds
        the MME template rendering task to the playbook.

        Raises:
            NFVCLCoreException: if no slice profiles are defined in the current config.

        Args:
            ansible_builder: The playbook builder to append tasks to.
        """
        if not self.amarisoft_5g_state.current_config.config.sliceProfiles:
            raise NFVCLCoreException("No slice profiles found in the configuration")

        pdn_list = self._build_pdn_list()
        amf_slice_list = self._build_amf_slice_list()

        ansible_builder.set_var("pdn_list", json5.dumps(to_serializable(pdn_list), indent=2))
        ansible_builder.set_var("amf_slices", json5.dumps(to_serializable(amf_slice_list), indent=2))
        ansible_builder.add_template_task(
            rel_path("config/mme.cfg.jinja2"),
            f"{self.config_dest_path}/{MME_FILE_NAME}"
        )

    def _build_pdn_list(self) -> list[PDNConfig]:
        """
        Constructs the list of PDNConfig objects representing the data networks
        served by this Amarisoft core.

        For each configured data network the usable IP pool is derived from the
        first pool CIDR:

        - ``first_ip = subnet[2]``, ``last_ip = subnet[-2]``

        Both boundaries are chosen to be even addresses because
        ``ip_addr_shift=1`` causes Amarisoft to allocate UE addresses in
        blocks of 2 (2^1), so the pool must start and end on an even address.

        Each PDN entry is then linked to all slice profiles whose DNN list
        includes that data network, with a default QoS flow per (PDN, slice)
        pair.

        Returns:
            A list of PDNConfig, one per data network, with slice associations
            populated.
        """
        pdn_list: list[PDNConfig] = []
        for data_net in self.amarisoft_5g_state.current_config.config.network_endpoints.data_nets:
            pool_net = IPv4Network(data_net.pools[0].cidr)
            # subnet[2] and subnet[-2]: first and last even addresses in the pool,
            # required by ip_addr_shift=1 (2-address block allocation)
            first_ip, last_ip = pool_net[2], pool_net[-2]

            pdn = PDNConfig(
                access_point_name=data_net.dnn,
                first_ip_addr=str(first_ip),
                last_ip_addr=str(last_ip),
                ip_addr_shift=1,
                dns_addr=data_net.dns
            )

            # Attach a slice entry for every profile that includes this DNN
            for slice_profile in self.amarisoft_5g_state.current_config.config.sliceProfiles:
                if data_net.dnn in slice_profile.dnnList:
                    snssai = SNSSAI(sst=slice_profile.sliceType, sd=sd_to_int(slice_profile.sliceId))
                    pdn.slices.append(PdnSlice(snssai=snssai, qos_flows=[QoSFlow()]))

            pdn_list.append(pdn)
        return pdn_list

    def _build_amf_slice_list(self) -> list[SNSSAI]:
        """
        Builds the flat list of SNSSAI entries that the AMF will advertise.

        One entry is created for each configured slice profile, regardless of
        which DNNs it is associated with.

        Returns:
            A list of SNSSAI objects.
        """
        return [
            SNSSAI(sst=sp.sliceType, sd=sd_to_int(sp.sliceId))
            for sp in self.amarisoft_5g_state.current_config.config.sliceProfiles
        ]

    def _add_route_tasks(self, ansible_builder: AnsiblePlaybookBuilder):
        """
        Injects the routing variables and adds the route-script and systemd
        service deployment tasks to the playbook.

        Steps added:

        1. Create ``/root/scripts/`` on the remote VM.
        2. Render and deploy ``start.sh`` — sets up IP routes via the router
           (waits for ``tun0``, then installs gNB and default routes).
        3. Render and deploy ``stop.sh`` — removes the IP policy rule on stop.
        4. Make both scripts executable.
        5. Render and deploy the ``routes.service`` systemd unit.
        6. Reload systemd and ensure the service is started and enabled at boot.

        Args:
            ansible_builder: The playbook builder to append tasks to.
        """
        ansible_builder.set_var("gnb_cidr", self.gnb_cidr)
        ansible_builder.set_var("n3_gateway", self.n3_gateway)
        ansible_builder.set_var("n6_gateway", self.n6_gateway)

        ansible_builder.add_shell_task("mkdir -p /root/scripts")
        ansible_builder.add_template_task(rel_path("config/start.sh.jinja2"), "/root/scripts/start.sh")
        ansible_builder.add_template_task(rel_path("config/stop.sh.jinja2"), "/root/scripts/stop.sh")
        ansible_builder.add_shell_task("chmod +x /root/scripts/start.sh /root/scripts/stop.sh")
        ansible_builder.add_template_task(rel_path("config/routes.service.jinja2"), "/etc/systemd/system/routes.service")
        ansible_builder.add_shell_task("systemctl daemon-reload")
        ansible_builder.add_service_task("routes", ServiceState.STARTED, True)
