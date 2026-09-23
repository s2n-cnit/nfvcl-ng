import asyncio
import time
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, cast

from pydantic import Field

from nfvcl_common.cloudinit_builder import CloudInit, CloudInitNetworkRoot
from nfvcl_core_models.providers.providers import ProviderData
from nfvcl_core_models.resources import ContainerResource, ContainerStatus, LXCContainerResource, LXCImage, NetResource, NetworkInterface, NetworkInterfaceAddress, HelmChartResource, VmPowerStatus
from nfvcl_core_models.vim.vim_models import VimTypeEnum
from nfvcl_providers.containerization.containerization_provider_interface import ContainerizationProviderData, ContainerizationProviderException, ContainerizationProviderInterface
from nfvcl_providers.containerization.incus.models.models import (
    IncusContainerConfig,
    IncusContainerDiskDevice,
    IncusContainerNicDevice,
    IncusContainerSpec,
    IncusByteSize,
    IncusByteUnit,
    IncusNetworkConfig,
    IncusNetworkType,
    IncusIpRange,
    IncusImageType,
)
from nfvcl_providers.vim_clients.incus_vim_client import IncusVimClient
from nfvcl_providers.virtualization.common.utils import check_ssh_ready


class ResourceGroupContainerizationProviderDataIncus(ProviderData):
    incus_dict: Dict[str, str] = Field(default_factory=dict)
    incus_networks: Dict[str, str] = Field(default_factory=dict)


class IncusVimProviderData(ProviderData):
    resource_groups: Dict[str, ResourceGroupContainerizationProviderDataIncus] = Field(default_factory=dict)

    def get_resource_group_data(self, resource_group: str) -> ResourceGroupContainerizationProviderDataIncus:
        if resource_group not in self.resource_groups:
            self.resource_groups[resource_group] = ResourceGroupContainerizationProviderDataIncus()
        return self.resource_groups[resource_group]


class ContainerizationProviderDataIncus(ContainerizationProviderData):
    vims: Dict[str, IncusVimProviderData] = Field(default_factory=dict)

    def get_vim_data(self, vim_name: str) -> IncusVimProviderData:
        if vim_name not in self.vims:
            self.vims[vim_name] = IncusVimProviderData()
        return self.vims[vim_name]


class ContainerizationProviderIncusException(ContainerizationProviderException):
    pass


class ContainerProviderIncus(ContainerizationProviderInterface):
    provider_vim_type = VimTypeEnum.INCUS
    data: ContainerizationProviderDataIncus

    CREATE_TIMEOUT = 120
    STATE_TIMEOUT = 30
    STOP_TIMEOUT = 30

    CLOUD_INIT_TIMEOUT = 300

    def init(self):
        self.data: ContainerizationProviderDataIncus = ContainerizationProviderDataIncus()
        self._loop = asyncio.new_event_loop()

    def _wait_for(self, condition, timeout: int, description: str = "") -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if condition():
                return True
            time.sleep(1)
        if description:
            self.logger.warning(f"Timed out waiting for: {description}")
        return False

    def _get_client(self, area: int) -> IncusVimClient:
        return cast(IncusVimClient, self.get_vim_client(area))

    def _get_resource_group_data(self, client: IncusVimClient, resource_group: str) -> ResourceGroupContainerizationProviderDataIncus:
        return self.data.get_vim_data(client.vim.name).get_resource_group_data(resource_group)

    def _delete_resource_group_data(self, client: IncusVimClient, resource_group: str):
        return self.data.get_vim_data(client.vim.name).resource_groups.pop(resource_group, None)

    def _run_async(self, coro):
        return self._loop.run_until_complete(coro)

    def _resolve_incus_network_name(self, rg_data: ResourceGroupContainerizationProviderDataIncus, network_name: str) -> str:
        return rg_data.incus_networks.get(network_name, network_name)

    def _ensure_lxc_image(self, client: IncusVimClient, image: LXCImage) -> None:
        """Ensure the image alias is present on the Incus server, downloading it if missing.

        Args:
            client: The Incus VIM client.
            image: The image descriptor (alias name and optional download URL).

        Raises:
            ContainerizationProviderIncusException: If the image is missing and
                cannot be downloaded (no URL provided or the import failed).
        """
        if self._run_async(client.get_image_by_name(name=image.name)) is not None:
            self.logger.info(f"Image '{image.name}' already present on the Incus server")
            return

        if not image.url:
            raise ContainerizationProviderIncusException(f"Image '{image.name}' not found on the Incus server and no URL provided to download it")

        self.logger.info(f"Image '{image.name}' not found, downloading it from {image.url}")
        fingerprint = self._run_async(client.import_image_from_archive(
            url=image.url,
            alias=image.name
        ))
        if fingerprint is None:
            raise ContainerizationProviderIncusException(f"Failed to download and import image '{image.name}'")
        self.logger.success(f"Image '{image.name}' downloaded and imported")

    def _get_managed_networks(self, area: int) -> Set[str]:
        """Return the names of the managed Incus networks present on the server for the area.

        ``GET /1.0/networks`` also lists unmanaged host interfaces (e.g. ``usb0``, ``eth0``,
        ``wlan0``) with ``managed: false``. Only networks with ``managed: true`` can be attached
        with the ``network`` key; unmanaged interfaces must be passed through with
        ``nictype: physical``. Managed status is taken from the ``managed`` field of the API,
        never inferred from the network type.
        """
        client = self._get_client(area)
        managed = set()
        for name in self._run_async(client.list_networks()):
            net = self._run_async(client.get_network(name=name))
            if net is not None and net.managed:
                managed.add(name)
        return managed

    def _build_nic_device(self, area: int, network_name: str, iface_name: str) -> IncusContainerNicDevice:
        """Build a NIC device, dynamically detecting whether the name refers to a managed Incus
        network (virtual NIC) or to an unmanaged host interface (physical passthrough)."""
        client = self._get_client(area)
        net_info = self._run_async(client.get_network(name=network_name))

        kwargs: dict = {"name": iface_name}
        if net_info is not None and net_info.managed:
            kwargs["network"] = network_name
            if net_info.config and "bridge.mtu" in net_info.config:
                kwargs["mtu"] = net_info.config["bridge.mtu"]
            self.logger.debug(f"Attaching {iface_name} to managed network {network_name}")
        else:
            kwargs["nictype"] = "physical"
            kwargs["parent"] = network_name
            self.logger.debug(f"Attaching {iface_name} to physical interface {network_name}")
        return IncusContainerNicDevice(**kwargs)

    def _build_container_spec(self, container_resource: LXCContainerResource, mgt_incus_net: str, rg_data: ResourceGroupContainerizationProviderDataIncus) -> IncusContainerSpec:
        config = IncusContainerConfig() \
            .set_cpu_limit(container_resource.flavor.cpu_count) \
            .set_memory_limit(IncusByteSize(value=container_resource.flavor.memory_mb, unit=IncusByteUnit.MIB))

        if container_resource.docker:
            config.set_flags(security_nesting=True,
                             security_syscalls_intercept_mknod=True, security_syscalls_intercept_setxattr=True)
        if container_resource.privileged:
            config.set_flags(security_privileged=True)

        spec = IncusContainerSpec(config=config)
        spec.add_disk_device(name="root", device=IncusContainerDiskDevice(path="/", pool="default", size=IncusByteSize(value=container_resource.flavor.storage_gb, unit=IncusByteUnit.GIB)))
        spec.add_nic_device(name="eth0", device=self._build_nic_device(container_resource.area, mgt_incus_net, "eth0"))

        for idx, net in enumerate(container_resource.additional_networks):
            incus_net = self._resolve_incus_network_name(rg_data, net)
            iface_name = f"eth{idx + 1}"
            spec.add_nic_device(name=iface_name, device=self._build_nic_device(container_resource.area, incus_net, iface_name))

        return spec

    def _build_cloud_init_config(self, container_resource: LXCContainerResource) -> IncusContainerConfig:
        """Build the cloud-init (user-data + network-config) for the container.

        The network-config matches each interface by its name (``eth0``,
        ``eth1``, ...), which Incus pins via the NIC device ``name`` property,
        with the non-management interfaces set to not override the default route.

        Args:
            container_resource: The container being created.

        Returns:
            An :class:`IncusContainerConfig` holding only the cloud-init keys.
        """
        # user-data: hostname + user/password
        user_cloud_init = CloudInit(hostname=container_resource.name)
        user_cloud_init.add_user(container_resource.username, container_resource.password)

        # network-config: DHCP on each interface, matched by its (pinned) name
        all_ifaces = ["eth0"] + [f"eth{idx + 1}" for idx in range(len(container_resource.additional_networks))]
        net_cloud_init = CloudInitNetworkRoot()
        for idx, iface in enumerate(all_ifaces):
            net_cloud_init.add_device_by_name(iface, override=(iface != "eth0"))

        cloud_init_config = IncusContainerConfig()
        cloud_init_config.set_cloud_init(
            user_data=user_cloud_init.build_cloud_config(),
            network_config=net_cloud_init.build_cloud_config(),
        )
        return cloud_init_config

    def create_container(self, container_resource: ContainerResource):
        if isinstance(container_resource, LXCContainerResource):
            self._create_lxc_container(container_resource)
        else:
            raise ContainerizationProviderIncusException(f"Unsupported container resource type: {type(container_resource)}")

    def pre_creation_check(self, container_resource: LXCContainerResource):
        """Verify that every managed network required by the container exists on the Incus server.

        Physical host interfaces (passed through via ``nictype: physical``) are
        skipped — only Incus-managed networks are validated.

        Args:
            container_resource: The container about to be created.

        Raises:
            ContainerizationProviderIncusException: If one or more managed networks
                are missing on the Incus server.
        """
        client = self._get_client(container_resource.area)
        all_networks = set(container_resource.get_all_connected_network_names())
        managed_networks = all_networks & self._get_managed_networks(container_resource.area)
        if not managed_networks:
            return

        all_exist, missing = self.check_networks_exist(
            container_resource.area,
            managed_networks,
            container_resource.resource_group,
        )
        if not all_exist:
            raise ContainerizationProviderIncusException(f"Cannot create container {container_resource.name}: missing networks on the Incus server: {', '.join(sorted(missing))}")

    def _create_lxc_container(self, container_resource: LXCContainerResource):
        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        self.logger.info(f"Creating container {container_resource.name}")

        instance_name = container_resource.get_name_k8s_format()

        # Idempotency: if the instance already exists, skip creation
        existing = self._run_async(client.get_istance(name=instance_name))
        if existing:
            self.logger.info(f"Container instance {instance_name} already exists, skipping creation")
            rg_data.incus_dict[container_resource.id] = instance_name
            self._update_net_info_from_instance(client, container_resource)
            container_resource.created = True
            self.save_to_db()
            return

        # Make sure all required networks exist before creating the container
        self.pre_creation_check(container_resource)

        # Make sure the image alias exists on the server, downloading it if needed
        self._ensure_lxc_image(client, container_resource.image)

        # Build container spec AND cloud-init config, including both in the
        # creation request so no subsequent PUT/PATCH config update is needed.
        cloud_init_config = self._build_cloud_init_config(container_resource)
        mgt_incus_net = self._resolve_incus_network_name(rg_data, container_resource.management_network)
        spec = self._build_container_spec(container_resource, mgt_incus_net, rg_data)
        if spec.config:
            spec.config.set_cloud_init(
                user_data=cloud_init_config.cloud_init_user_data,
                network_config=cloud_init_config.cloud_init_network_config,
            )
        else:
            spec.config = cloud_init_config

        spec_config = spec.config.to_incus_dict() if spec.config else None
        spec_devices = {dev_name: dev.to_incus_dict() for dev_name, dev in spec.devices.items()} if spec.devices else None
        self.logger.debug(f"Container spec for {instance_name}: config={spec_config} devices={spec_devices}")

        result = self._run_async(client.create_container(
            name=instance_name,
            image_name=container_resource.image.name,
            container_spec=spec,
            start=False,
        ))

        if result is None:
            raise ContainerizationProviderIncusException(f"Failed to create container {container_resource.name}")

        rg_data.incus_dict[container_resource.id] = instance_name
        self.save_to_db()

        if not self._run_async(client.start_instance(name=instance_name)):
            raise ContainerizationProviderIncusException(f"Failed to start container {container_resource.name}")

        expected_ifaces = ["eth0"] + [f"eth{idx + 1}" for idx in range(len(container_resource.additional_networks))]
        self._wait_for_cloud_init(client, instance_name, expected_ifaces)

        self._update_net_info_from_instance(client, container_resource)

        container_resource.created = True
        self.logger.success(f"Creating container {container_resource.name} finished")
        self.save_to_db()

    def _wait_for_cloud_init(self, client: IncusVimClient, instance_name: str, expected_ifaces: List[str]):
        """Poll ``get_instance_state`` until every expected interface has an IPv4 address.

        Cloud-init runs on first boot and configures networking. Once each
        interface (``eth0``, ``eth1``, ...) is assigned an IPv4 address, we
        know cloud-init has finished its network configuration.

        Args:
            client: The Incus VIM client.
            instance_name: The Incus instance name.
            expected_ifaces: List of interface names that should get an IP
                (e.g. ``["eth0", "eth1"]``).
        """
        def _all_ifaces_have_ipv4():
            state = self._run_async(client.get_instance_state(name=instance_name))
            if state is None or not state.network:
                return False
            for iface in expected_ifaces:
                iface_data = state.network.get(iface)
                if not iface_data or not iface_data.addresses:
                    return False
                if not any(addr.family == "inet" for addr in iface_data.addresses):
                    return False
            return True

        if not self._wait_for(
            _all_ifaces_have_ipv4,
            self.CLOUD_INIT_TIMEOUT,
            f"cloud-init to complete on {instance_name}",
        ):
            raise ContainerizationProviderIncusException(f"Timed out waiting for cloud-init on {instance_name}")

    def _update_net_info_from_instance(self, client: IncusVimClient, container_resource: LXCContainerResource):
        instance_name = container_resource.get_name_k8s_format()

        instance_state = None
        deadline = time.time() + self.STATE_TIMEOUT
        while time.time() < deadline:
            instance_state = self._run_async(client.get_instance_state(name=instance_name))
            if instance_state is not None and instance_state.network:
                break
            time.sleep(1)

        if instance_state is None:
            self.logger.warning(f"Instance {instance_name} not found, cannot update network info")
            return

        container_resource.network_interfaces.clear()

        if instance_state.network:
            for iface_name, iface_data in instance_state.network.items():
                if iface_data.addresses:
                    for addr in iface_data.addresses:
                        if addr.family != "inet":
                            continue
                        mac = iface_data.hwaddr
                        ip_str = addr.address
                        netmask = addr.netmask or "24"

                        fixed = NetworkInterfaceAddress(
                            interface_name=iface_name,
                            mac=mac,
                            ip=ip_str,
                            cidr=f"{ip_str}/{netmask}",
                        )
                        if ip_str not in [ni.fixed.ip for interfaces in container_resource.network_interfaces.values() for ni in interfaces]:
                            net_name = self._resolve_network_name_for_iface(container_resource, iface_name, iface_data)
                            if net_name not in container_resource.network_interfaces:
                                container_resource.network_interfaces[net_name] = []
                            container_resource.network_interfaces[net_name].append(NetworkInterface(fixed=fixed))

        mgt_interface = container_resource.network_interfaces.get(container_resource.management_network, [])
        if mgt_interface:
            container_resource.access_ip = mgt_interface[0].fixed.ip

    def _resolve_network_name_for_iface(self, container_resource: LXCContainerResource, iface_name: str, iface_data) -> str:
        if iface_name == "lo":
            return iface_data.host_name or "lo"
        if iface_name == "eth0" and container_resource.management_network:
            return container_resource.management_network
        if iface_name.startswith("eth") and container_resource.additional_networks:
            try:
                idx = int(iface_name.replace("eth", ""))
                if 0 < idx <= len(container_resource.additional_networks):
                    return container_resource.additional_networks[idx - 1]
            except ValueError:
                pass
        return iface_data.host_name or iface_name

    def get_container_interface_name_from_parent(self, container_resource: LXCContainerResource, parent_interface: str) -> Optional[str]:
        """Return the name of the container-side interface attached to the given parent.

        The parent is the host-side interface/network the NIC device is connected to:
        ``parent`` for physical passthrough NICs, ``network`` for NICs attached to a
        managed Incus network. The mapping is resolved from the NIC devices of the
        running instance, falling back to the standard naming convention where
        ``eth0`` is the management interface and each additional network (in
        ``additional_networks`` order) gets ``eth1``, ``eth2``, ... .

        Args:
            container_resource: The container whose interfaces are examined.
            parent_interface: Name of the host-side interface/network.

        Returns:
            The interface name as seen inside the container (e.g. ``"eth1"``),
            or ``None`` if no NIC attached to ``parent_interface`` is found.
        """
        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        instance_name = container_resource.get_name_k8s_format()
        resolved_parent = self._resolve_incus_network_name(rg_data, parent_interface)
        candidates = {parent_interface, resolved_parent}

        instance = self._run_async(client.get_istance(name=instance_name))
        if instance is not None and getattr(instance, "devices", None):
            for dev_name, dev in instance.devices.items():
                if not isinstance(dev, dict) or dev.get("type") != "nic":
                    continue
                if dev.get("parent") in candidates or dev.get("network") in candidates:
                    return dev_name

        if parent_interface == container_resource.management_network:
            return "eth0"
        try:
            idx = container_resource.additional_networks.index(parent_interface)
        except ValueError:
            return None
        return f"eth{idx + 1}"

    def pull_container_results(self, container_resource: LXCContainerResource, local_dir: str | Path = "results", remote_dir: str = "/root/ExperimentsResults", timeout: int = 300) -> Optional[Path]:
        """Pull the most recent experiment results archive from a container.

        Finds the newest ``*.tar.gz`` archive in ``remote_dir`` inside the
        container and downloads it to
        ``local_dir/<container_name>/<archive_name>`` on the machine running
        this provider (parent directories are created). If no archive is found
        or the transfer fails, a warning is logged and ``None`` is returned.

        Args:
            container_resource: The container holding the experiment results.
            local_dir: Base directory where the per-container subdirectory is created.
            remote_dir: Directory inside the container containing the result archives.
            timeout: Seconds to wait for the listing and the transfer.

        Returns:
            The local path of the downloaded archive, or ``None`` if there is
            nothing to pull or the pull failed.
        """
        client = self._get_client(container_resource.area)
        instance_name = container_resource.get_name_k8s_format()

        listing = self._run_async(client.exec_command(
            name=instance_name,
            command=["sh", "-c", f"ls -1t {remote_dir}/*.tar.gz 2>/dev/null | head -n 1"],
            timeout=timeout,
        ))
        archive_path = ""
        if listing:
            for line in reversed(listing.splitlines()):
                line = line.strip()
                if line.endswith(".tar.gz"):
                    archive_path = line
                    break

        if not archive_path:
            self.logger.warning(f"No experiment results archive found in '{remote_dir}' on container {container_resource.name}")
            return None

        destination = Path(local_dir) / container_resource.name.lower() / Path(archive_path).name
        if not self._run_async(client.pull_file(name=instance_name, remote_path=archive_path, local_path=destination, timeout=timeout)):
            self.logger.warning(f"Failed to pull experiment results '{archive_path}' from container {container_resource.name}")
            return None

        self.logger.success(f"Experiment results from container {container_resource.name} saved to '{destination}'")
        return destination

    def destroy_container(self, container_resource: ContainerResource):
        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        self.logger.info(f"Destroying container {container_resource.name}")

        instance_name = container_resource.get_name_k8s_format()
        try:
            self._run_async(client.stop_instance(name=instance_name, force=True))
        except Exception as e:
            self.logger.warning(f"Unable to stop container {container_resource.name}: {e}")
        try:
            self._run_async(client.delete_container(name=instance_name))
        except Exception as e:
            self.logger.warning(f"Unable to delete container {container_resource.name}: {e}")

        if container_resource.id in rg_data.incus_dict:
            rg_data.incus_dict.pop(container_resource.id)

        self.logger.success(f"Destroying container {container_resource.name} finished")
        self.save_to_db()

    def reboot_container(self, container_resource: ContainerResource, hard: bool = False):
        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        self.logger.info(f"Restarting container {container_resource.name}")

        instance_name = container_resource.get_name_k8s_format()
        if container_resource.id in rg_data.incus_dict:
            self._run_async(client.restart_instance(name=instance_name, force=hard))
            self.logger.success(f"Container {instance_name} restarted")
        else:
            raise ContainerizationProviderIncusException(f"Container {container_resource.name} not found")

    def check_container_status(self, container_resource: ContainerResource) -> ContainerStatus:
        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        self.logger.info(f"Checking status of container {container_resource.name}")

        instance_name = container_resource.get_name_k8s_format()

        if container_resource.id not in rg_data.incus_dict:
            self.logger.warning(f"Container {container_resource.name} not tracked in incus_dict, returning UNKNOWN")
            return ContainerStatus(vm_name=container_resource.name, power_status=VmPowerStatus.UNKNOWN, ssh_reachable=False)

        instance = self._run_async(client.get_istance(name=instance_name))
        if instance is None:
            self.logger.warning(f"Instance {instance_name} not found on Incus, returning UNKNOWN")
            return ContainerStatus(vm_name=container_resource.name, power_status=VmPowerStatus.UNKNOWN, ssh_reachable=False)

        incus_status = instance.status.upper()

        if incus_status in ("RUNNING",):
            power_status = VmPowerStatus.RUNNING
        elif incus_status in ("STOPPED", "SHUTOFF"):
            power_status = VmPowerStatus.SHUTOFF
        else:
            power_status = VmPowerStatus.UNKNOWN

        ssh_reachable = False
        if power_status == VmPowerStatus.RUNNING and isinstance(container_resource, LXCContainerResource) and container_resource.access_ip:
            try:
                ssh_reachable = check_ssh_ready(
                    host=container_resource.access_ip,
                    port=22,
                    user=container_resource.username,
                    passwd=container_resource.password,
                    logger_override=self.logger,
                )
            except (OSError, Exception) as e:
                self.logger.warning(f"SSH check failed for {container_resource.name}: {e}")

        self.logger.info(f"Container {container_resource.name} status: incus_status={incus_status}, mapped_status={power_status}, ssh_reachable={ssh_reachable}")

        return ContainerStatus(
            vm_name=container_resource.name,
            power_status=power_status,
            ssh_reachable=ssh_reachable,
        )

    def create_net(self, net_resource: NetResource):
        client = self._get_client(net_resource.area)
        rg_data = self._get_resource_group_data(client, net_resource.resource_group)

        network_name = net_resource.get_name_k8s_format()

        existing = self._run_async(client.get_network(name=network_name))
        if existing:
            self.logger.info(f"Network {network_name} already exists, skipping creation")
            rg_data.incus_networks[net_resource.name] = network_name
            self.save_to_db()
            return

        self.logger.info(f"Creating network {net_resource.name} ({network_name})")

        cidr = net_resource.cidr
        parts = cidr.split("/")
        ip = parts[0]
        prefix = int(parts[1]) if len(parts) > 1 else 24

        gateway_parts = ip.split(".")
        gateway_parts[-1] = str(int(gateway_parts[-1]) + 1)
        gateway = ".".join(gateway_parts)

        dhcp_start_parts = ip.split(".")
        dhcp_start_parts[-1] = str(int(dhcp_start_parts[-1]) + 100)
        dhcp_start = ".".join(dhcp_start_parts)

        dhcp_end_parts = ip.split(".")
        dhcp_end_parts[-1] = str(int(dhcp_end_parts[-1]) + 200)
        dhcp_end = ".".join(dhcp_end_parts)

        if net_resource.allocation_pool:
            dhcp_start = net_resource.allocation_pool.start.exploded
            dhcp_end = net_resource.allocation_pool.end.exploded

        network_config = IncusNetworkConfig().set_ipv4(
            address=f"{gateway}/{prefix}",
            nat=False,
            dhcp=True,
            dhcp_ranges=[IncusIpRange(start=dhcp_start, end=dhcp_end)],
        )

        result = self._run_async(client.add_network(
            name=network_name,
            network_type=IncusNetworkType.BRIDGE,
            config=network_config,
        ))

        if not result:
            raise ContainerizationProviderIncusException(f"Failed to create network {net_resource.name}")

        rg_data.incus_networks[net_resource.name] = network_name
        self.logger.success(f"Creating network {net_resource.name} finished")
        self.save_to_db()

    def _apply_netplan_config(self, client: IncusVimClient, instance_name: str, container_resource: LXCContainerResource, timeout: int = 30) -> None:
        all_ifaces = ["eth0"] + [f"eth{idx + 1}" for idx in range(len(container_resource.additional_networks))]
        net_cloud_init = CloudInitNetworkRoot()
        for iface in all_ifaces:
            net_cloud_init.add_device_by_name(iface, override=(iface != "eth0"))

        netplan_yaml = net_cloud_init.build_cloud_config()
        netplan_file = "/etc/netplan/50-cloud-init.yaml"

        write_cmd = ["sh", "-c", f"cat > {netplan_file} << 'EOF'\n{netplan_yaml}EOF\n"]
        write_output = self._run_async(client.exec_command(name=instance_name, command=write_cmd, timeout=timeout))
        if write_output is None:
            self.logger.warning(f"Failed to write netplan config on {instance_name}")
            return

        apply_cmd = ["sh", "-c", "netplan apply"]
        apply_output = self._run_async(client.exec_command(name=instance_name, command=apply_cmd, timeout=timeout))
        if apply_output is not None:
            self.logger.debug(f"netplan apply on {instance_name}: {apply_output or '<no output>'}")
        else:
            self.logger.warning(f"netplan apply failed on {instance_name}")

    def attach_nets(self, container_resource: ContainerResource, nets_name: List[str]) -> List[str]:
        if not isinstance(container_resource, LXCContainerResource):
            raise ContainerizationProviderIncusException(f"Unsupported container resource type: {type(container_resource)}")

        client = self._get_client(container_resource.area)
        rg_data = self._get_resource_group_data(client, container_resource.resource_group)
        self.logger.info(f"Attaching networks {nets_name} to container {container_resource.name}")

        instance_name = container_resource.get_name_k8s_format()

        managed_networks = self._get_managed_networks(container_resource.area)

        for net in nets_name:
            idx = len(container_resource.additional_networks) + 1
            iface_name = f"eth{idx}"
            incus_net = self._resolve_incus_network_name(rg_data, net)

            if incus_net in managed_networks:
                attached = self._run_async(client.attach_network_to_instance(instance_name, iface_name, incus_net))
            else:
                attached = self._run_async(client.attach_physical_interface_to_instance(instance_name, iface_name, net))

            if not attached:
                raise ContainerizationProviderIncusException(f"Failed to attach network {net} ({iface_name} -> {incus_net}) to container {container_resource.name}")

            container_resource.additional_networks.append(net)

        self._apply_netplan_config(client, instance_name, container_resource)
        self._update_net_info_from_instance(client, container_resource)
        self.save_to_db()

        ips = []
        for net in nets_name:
            for iface in container_resource.network_interfaces.get(net, []):
                ips.append(iface.fixed.ip)

        self.logger.success(f"Networks {', '.join(nets_name)} attached to container {container_resource.name}")
        return ips

    def check_networks_exist(self, area: int, networks_to_check: set[str], resource_group: Optional[str] = None) -> Tuple[bool, Set[str]]:
        client = self._get_client(area)
        listed_networks = set(self._run_async(client.list_networks()))
        managed_networks = self._get_managed_networks(area)

        rg_data = None
        if resource_group is not None:
            rg_data = self._get_resource_group_data(client, resource_group)

        missing: Set[str] = set()
        for net in networks_to_check:
            incus_name = rg_data.incus_networks.get(net, net.lower().replace("_", "-")) if rg_data else net.lower().replace("_", "-")
            if incus_name in managed_networks or net in managed_networks:
                continue
            if incus_name in listed_networks or net in listed_networks:
                continue  # unmanaged host interface (e.g. physical NIC), skipped from managed-network validation
            missing.add(net)

        return len(missing) == 0, missing

    def cleanup_resource_group(self, resource_group: str):
        for vim_name, vim_data in list(self.data.vims.items()):
            rg_data = vim_data.resource_groups.get(resource_group)
            if rg_data is None:
                continue

            client = cast(
                IncusVimClient,
                self.vim_client_pool.get_client_by_vim_name(vim_name, self.provider_vim_type),
            )

            for vm_resource_id, instance_name in list(rg_data.incus_dict.items()):
                try:
                    self.logger.warning(f"Deleting leftover container {instance_name}, something did go wrong in the blueprint deletion")
                    self._run_async(client.delete_container(name=instance_name))
                    del rg_data.incus_dict[vm_resource_id]
                except Exception as e:
                    self.logger.error(f"Unable to delete leftover container {instance_name}: {e}")

            for net_name, incus_net in list(rg_data.incus_networks.items()):
                try:
                    self.logger.warning(f"Deleting leftover network {incus_net}")
                    self._run_async(client.delete_network(name=incus_net))
                    del rg_data.incus_networks[net_name]
                except Exception as e:
                    self.logger.error(f"Unable to delete leftover network {incus_net}: {e}")

            self._delete_resource_group_data(client, resource_group)
        self.save_to_db()
