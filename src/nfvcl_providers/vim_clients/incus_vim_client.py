import asyncio
import hashlib
import io
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Optional, List

import httpx
import pyincusd
from pydantic import StrictStr
from pyincusd import Instance, Image, InstanceStatePut
from pyincusd.models.instance_exec_post import InstanceExecPost
from pyincusd.models.instance_put import InstancePut
from pyincusd.models.instances_post import InstancesPost, InstanceSource
from pyincusd.models.network import Network
from pyincusd.models.networks_post import NetworksPost
from pyincusd.models.server import Server

from nfvcl_core_models.vim.vim_models import VimModel
from nfvcl_providers.containerization.incus.models.models import (
    IncusArchitecture,
    IncusImageType,
    IncusNetworkConfig,
    IncusNetworkType,
    IncusOsName,
    IncusUbuntuRelease,
    IncusVmSpec, IncusContainerSpec, )
from nfvcl_providers.vim_clients.vim_client import VimClient


class IncusVimClient(VimClient):
    """VIM client for an Incus server.

    Wraps the ``pyincusd`` async API to manage images and instances (containers
    and virtual machines) on a remote Incus host authenticated with TLS client
    certificates.

    Note on async operations: many Incus endpoints are asynchronous and return a
    response whose ``status_code`` is ``100`` ("Operation created", HTTP 202)
    rather than ``200``; the methods below check for ``100`` to confirm the
    operation was accepted.
    """

    def __init__(self, vim: VimModel):
        """Initialize the client and open the connection to the Incus server.

        Args:
            vim: The VIM model holding the Incus connection parameters (URL,
                port and TLS client cert/key + CA certificate).
        """
        super().__init__(vim)
        self.version = None
        self.nfvcl_runtime_ready = False
        self._incus_client: Optional[pyincusd.ApiClient] = None
        self.crt_path: Optional[Path] = None
        self.key_path: Optional[Path] = None
        self.ca_path: Optional[Path] = None
        self.connect_incus()

    def connect_incus(self):
        """Establish the ``pyincusd`` API client, retrying on failure.

        Writes the TLS client certificate, key and CA certificate to temporary
        files (paths kept on the instance so they can be cleaned up in
        :meth:`close`) and builds a configured :class:`pyincusd.ApiClient`.
        Retries up to ``max_retries`` times before raising ``ConnectionError``.
        """
        connection_attempts = 0
        max_retries = 5
        while connection_attempts < max_retries:
            try:
                if self.vim.incus_parameters().cert_file and self.vim.incus_parameters().key_file and self.vim.incus_parameters().ssl_ca_cert:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as crt_file:
                        self.crt_path = Path(crt_file.name)
                        crt_file.write(self.vim.incus_parameters().cert_file)
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as key_file:
                        self.key_path = Path(key_file.name)
                        key_file.write(self.vim.incus_parameters().key_file)
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as ca_file:
                        self.ca_path = Path(ca_file.name)
                        ca_file.write(self.vim.incus_parameters().ssl_ca_cert)

                    configuration = pyincusd.Configuration(
                        host=f"https://{self.vim.vim_url}:{self.vim.incus_parameters().incus_port}"
                    )
                    configuration.cert_file = str(self.crt_path)
                    configuration.key_file = str(self.key_path)
                    configuration.ssl_ca_cert = str(self.ca_path)
                    configuration.verify_ssl = False
                    configuration.assert_hostname = True

                    self._incus_client = pyincusd.ApiClient(configuration)
                break
            except Exception as e:
                connection_attempts += 1
                self.logger.error(f"Failed to connect to Incus API: {e}. Attempt {connection_attempts} of {max_retries}")
                if connection_attempts >= max_retries:
                    raise ConnectionError("Failed to connect to Incus API after multiple attempts") from e
            time.sleep(3)

    async def get_server_info(self) -> Server | None:
        """Fetch server environment and configuration (equivalent to ``incus info``).

        Returns:
            The :class:`Server` metadata (including environment, config, API
            extensions), or ``None`` on failure.
        """
        api = pyincusd.ServerApi(self._incus_client)
        try:
            result = await api.server_get()
        except pyincusd.ApiException as e:
            self.logger.error(f"Failed to fetch server info: {e}")
            return None
        return result.metadata if result else None

    async def list_images(self) -> List[StrictStr]:
        """List the fingerprints of all images available on the Incus server.

        Returns:
            A list of image fingerprints (extracted from the API URLs), or an
            empty list if there are none.
        """
        api = pyincusd.ImagesApi(self._incus_client)
        images = await api.images_get()
        if not images or not images.metadata:
            return []
        return [url.split("/images/")[-1] for url in images.metadata]

    async def get_image(self, fingerprint: str) -> Image | None:
        """Fetch a single image by its fingerprint.

        Args:
            fingerprint: The image fingerprint to look up.

        Returns:
            The :class:`Image` metadata, or ``None`` if not found.
        """
        api = pyincusd.ImagesApi(self._incus_client)
        try:
            image = await api.image_get(fingerprint=fingerprint)
        except pyincusd.ApiException:
            return None
        return image.metadata if image else None

    async def get_image_by_name(self, name: str) -> Image | None:
        """Find an image whose alias matches the given name.

        Iterates over all images and their aliases looking for an exact alias
        name match.

        Args:
            name: The alias name to search for.

        Returns:
            The matching :class:`Image`, or ``None`` if no alias matches.
        """
        fingerprints = await self.list_images()
        for fingerprint in fingerprints:
            image = await self.get_image(fingerprint=fingerprint)
            if image and image.aliases:
                for alias in image.aliases:
                    if alias.name == name:
                        return image
        return None

    @staticmethod
    def _build_metadata_tarball(architecture: IncusArchitecture = IncusArchitecture.X86_64, os_name: IncusOsName = IncusOsName.UBUNTU, release: IncusUbuntuRelease | str = IncusUbuntuRelease.JAMMY) -> bytes:
        """Build the in-memory ``metadata.tar.xz`` required to import an image.

        Incus split-format image imports need a metadata tarball containing a
        ``metadata.yaml`` describing the image. This creates that tarball in
        memory (no temp file on disk).

        Args:
            architecture: Image architecture.
            os_name: Image OS name property.
            release: Image release property (enum or free string).

        Returns:
            The gzipped/xz-compressed tarball bytes.
        """
        architecture = IncusArchitecture(architecture).value
        os_name = IncusOsName(os_name).value
        release = release.value if isinstance(release, IncusUbuntuRelease) else str(release)
        metadata_yaml = (
            f"architecture: {architecture}\n"
            f"creation_date: {int(time.time())}\n"
            "properties:\n"
            f"  architecture: {architecture}\n"
            f"  description: {os_name} {release}\n"
            f"  os: {os_name}\n"
            f"  release: {release}\n"
        ).encode("utf-8")

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:xz") as tar:
            info = tarfile.TarInfo(name="metadata.yaml")
            info.size = len(metadata_yaml)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(metadata_yaml))
        return buffer.getvalue()

    @staticmethod
    def _compute_split_fingerprint(metadata_bytes: bytes, rootfs_bytes: bytes) -> str:
        """Compute the fingerprint of a split-format image.

        The Incus server hashes the metadata part followed by the rootfs part
        when importing a split-format image, so the fingerprint is
        ``sha256(metadata || rootfs)``.

        Args:
            metadata_bytes: The ``metadata.tar.xz`` bytes.
            rootfs_bytes: The rootfs bytes.

        Returns:
            The expected image fingerprint as a hex string.
        """
        return hashlib.sha256(metadata_bytes + rootfs_bytes).hexdigest()

    async def _ensure_image_alias(self, api: pyincusd.ImagesApi, alias: str, fingerprint: str) -> bool:
        """Ensure an alias exists for an image that is already present on the server.

        Args:
            api: The images API client.
            alias: The alias name to ensure.
            fingerprint: The target fingerprint for the alias.

        Returns:
            ``True`` if the alias already existed or was created successfully.
        """
        if await self.get_image_by_name(name=alias) is not None:
            return True
        try:
            await api.images_aliases_post(image_alias=pyincusd.models.ImageAliasesPost(name=alias, target=fingerprint))
            return True
        except pyincusd.ApiException as e:
            self.logger.error(f"Failed to create alias '{alias}' for image '{fingerprint}': {e}")
            return False

    async def import_image(self, url: str, alias: str, image_type: IncusImageType, architecture: IncusArchitecture, os_name: IncusOsName, release: IncusUbuntuRelease | str, public: bool = False, timeout: int = 600) -> str | None:
        """Download an image from a URL and import it into Incus (split format).

        Fetches the raw rootfs/disk from ``url``, builds a metadata tarball, and
        uploads both as a multipart ``POST /1.0/images`` request. The image type
        is derived from the rootfs multipart field name: Incus treats a field
        named ``rootfs`` as a container image and ``rootfs.img`` as a VM image.
        Waits for the import operation to complete before returning.

        This bypasses the generated ``images_post`` helper (which hardcodes the
        field name to ``rootfs``) so that VM images are correctly detected.

        Args:
            url: HTTP(S) URL of the image file to download.
            alias: Alias to assign to the imported image.
            image_type: Whether the image is a container or a virtual machine.
            architecture: Image architecture (stored in the metadata).
            os_name: Image OS name (stored in the metadata).
            release: Image release (stored in the metadata).
            public: Whether the image should be publicly available.
            timeout: Seconds to wait for the import operation to complete.

        Returns:
            The fingerprint of the imported image, or ``None`` on failure.
        """
        image_type = IncusImageType(image_type)
        async with httpx.AsyncClient(timeout=None, verify=False) as http_client:
            response = await http_client.get(url, follow_redirects=True)
            response.raise_for_status()
            rootfs_bytes = response.content

        metadata_bytes = self._build_metadata_tarball(architecture=architecture, os_name=os_name, release=release)

        # Incus detects the image type from the multipart form field NAME of the
        # rootfs part: "rootfs" -> container, "rootfs.img" -> virtual-machine.
        rootfs_field = "rootfs.img" if image_type == IncusImageType.VIRTUAL_MACHINE else "rootfs"

        api = pyincusd.ImagesApi(self._incus_client)
        fingerprint = self._compute_split_fingerprint(metadata_bytes=metadata_bytes, rootfs_bytes=rootfs_bytes)
        if await self.get_image(fingerprint=fingerprint) is not None:
            if not await self._ensure_image_alias(api, alias, fingerprint):
                return None
            self.logger.info(f"Image with fingerprint '{fingerprint}' already present on the Incus server")
            return fingerprint

        files = {
            "metadata": ("metadata.tar.xz", metadata_bytes),
            rootfs_field: (url.rsplit("/", 1)[-1], rootfs_bytes),
        }
        header_params = {
            "Accept": "application/json",
            "Content-Type": "multipart/form-data",
            "X-Incus-aliases": alias,
            "X-Incus-filename": url.rsplit("/", 1)[-1],
            "X-Incus-public": "true" if public else "false",
        }
        param = api.api_client.param_serialize(
            method="POST",
            resource_path="/1.0/images",
            header_params=header_params,
            files=files,
            auth_settings=[],
            _host=None,
        )
        response_data = await api.api_client.call_api(*param)
        await response_data.read()
        result = api.api_client.response_deserialize(
            response_data=response_data,
            response_types_map={
                "202": "ClusterMembersPost202Response",
                "400": "ServerPut400Response",
                "403": "ServerPut403Response",
                "500": "ServerGet500Response",
            },
        ).data
        if not result or result.status_code != 100:
            return None
        operation_url = getattr(result, "operation", None)
        if operation_url:
            if not await self._wait_for_operation(operation_url, timeout, f"Import of image '{alias}'"):
                # The server may have rejected the import because an image with
                # the same fingerprint already exists; recover by using the
                # locally computed fingerprint instead of failing.
                if await self.get_image(fingerprint=fingerprint) is not None:
                    if await self._ensure_image_alias(api, alias, fingerprint):
                        return fingerprint
                return None
            image = await self.get_image_by_name(name=alias)
            return image.fingerprint if image else None
        metadata = result.metadata
        if metadata and metadata.metadata and isinstance(metadata.metadata, dict):
            return metadata.metadata.get("fingerprint")
        return None

    async def import_image_from_archive(self, url: str, alias: str, public: bool = False, timeout: int = 600) -> str | None:
        """Download a simplified (unified) image tarball from a URL and import it into Incus.

        A simplified image is a single tarball (e.g. ``.tar.gz``) containing
        both the ``metadata.yaml`` and the rootfs (``rootfs/`` directory for
        containers, ``rootfs.img`` for VMs). It is uploaded as a raw
        ``application/octet-stream`` ``POST /1.0/images`` body, which Incus
        detects as a non-split image and inspects to derive type, architecture
        and other properties from the embedded ``metadata.yaml``. Waits for
        the import operation to complete before returning.

        This bypasses the generated ``images_post`` helper (which requires
        split ``metadata`` + ``rootfs`` multipart parts).

        Args:
            url: HTTP(S) URL of the simplified image tarball to download.
            alias: Alias to assign to the imported image.
            public: Whether the image should be publicly available.
            timeout: Seconds to wait for the import operation to complete.

        Returns:
            The fingerprint of the imported image, or ``None`` on failure.
        """
        async with httpx.AsyncClient(timeout=None, verify=False) as http_client:
            response = await http_client.get(url, follow_redirects=True)
            response.raise_for_status()
            image_bytes = response.content

        # Unified images are fingerprinted by the server as the sha256 of the
        # raw uploaded body, so the expected fingerprint can be computed here.
        fingerprint = hashlib.sha256(image_bytes).hexdigest()

        api = pyincusd.ImagesApi(self._incus_client)
        if await self.get_image(fingerprint=fingerprint) is not None:
            if not await self._ensure_image_alias(api, alias, fingerprint):
                return None
            self.logger.info(f"Image with fingerprint '{fingerprint}' already present on the Incus server")
            return fingerprint

        header_params = {
            "Accept": "application/json",
            "Content-Type": "application/octet-stream",
            "X-Incus-aliases": alias,
            "X-Incus-filename": url.rsplit("/", 1)[-1],
            "X-Incus-public": "true" if public else "false",
        }
        param = api.api_client.param_serialize(
            method="POST",
            resource_path="/1.0/images",
            header_params=header_params,
            body=image_bytes,
            auth_settings=[],
            _host=None,
        )
        response_data = await api.api_client.call_api(*param)
        await response_data.read()
        result = api.api_client.response_deserialize(
            response_data=response_data,
            response_types_map={
                "202": "ClusterMembersPost202Response",
                "400": "ServerPut400Response",
                "403": "ServerPut403Response",
                "500": "ServerGet500Response",
            },
        ).data
        if not result or result.status_code != 100:
            return None
        operation_url = getattr(result, "operation", None)
        if operation_url:
            if not await self._wait_for_operation(operation_url, timeout, f"Import of image '{alias}'"):
                # The server may have rejected the import because an image with
                # the same fingerprint already exists; recover by using the
                # locally computed fingerprint instead of failing.
                if await self.get_image(fingerprint=fingerprint) is not None:
                    if await self._ensure_image_alias(api, alias, fingerprint):
                        return fingerprint
                return None
            image = await self.get_image_by_name(name=alias)
            return image.fingerprint if image else None
        metadata = result.metadata
        if metadata and metadata.metadata and isinstance(metadata.metadata, dict):
            return metadata.metadata.get("fingerprint")
        return None

    async def list_istances(self) -> List[StrictStr]:
        """List all instances on the Incus server.

        Returns:
            The instances metadata (list of instance URLs), or an empty list.
        """
        api = pyincusd.InstancesApi(self._incus_client)
        istances = await api.instances_get()
        return istances.metadata if istances else []

    async def get_istance(self, name: str) -> Instance | None:
        """Fetch a single instance by name.

        Args:
            name: The instance name.

        Returns:
            The :class:`Instance` metadata, or ``None`` if not found.
        """
        api = pyincusd.InstancesApi(self._incus_client)
        try:
            istance = await api.instance_get(name=name)
        except pyincusd.ApiException:
            return None
        return istance.metadata if istance else None

    async def get_instance_state(self, name: str) -> pyincusd.models.InstanceState | None:
        """Fetch the runtime state of an instance by name.

        Returns network addresses, CPU/memory/disk usage counters, process count,
        etc. — the same data as ``incus info <name>`` Resources section.

        Args:
            name: The instance name.

        Returns:
            The :class:`InstanceState` metadata, or ``None`` if not found.
        """
        api = pyincusd.InstancesApi(self._incus_client)
        try:
            result = await api.instance_state_get(name=name)
        except pyincusd.ApiException:
            return None
        return result.metadata if result else None

    async def get_instance_info(self, name: str) -> tuple[Instance | None, pyincusd.models.InstanceState | None]:
        """Fetch the full instance info — metadata + runtime state.

        Returns the same combined data as ``incus info <name>``: the
        :class:`Instance` (config, devices, status, architecture, ...) and
        the :class:`InstanceState` (network IPs, resource usage, process
        count, ...).

        Args:
            name: The instance name.

        Returns:
            A tuple of ``(instance, state)``, each possibly ``None`` on failure.
        """
        instance = await self.get_istance(name)
        state = await self.get_instance_state(name)
        return instance, state

    async def update_instance_config(self, name: str, config_updates: dict, timeout: int = 120) -> bool:
        """Replace the instance config via PUT, merging ``config_updates`` into the existing config.

        Uses PUT (full replacement) because PATCH on clustered Incus triggers a
        backup write that fails when the storage pool is not local to this node.
        Waits for the update operation to complete.

        Args:
            name: The instance name.
            config_updates: Incus config keys to merge into the instance config.
            timeout: Seconds to wait for the update operation to complete.

        Returns:
            ``True`` if the update operation completed successfully.
        """
        instance = await self.get_istance(name)
        if instance is None:
            return False
        api = pyincusd.InstancesApi(self._incus_client)
        merged_config = {**(instance.config or {}), **config_updates}
        instance_put = InstancePut(
            config=merged_config,
            devices=instance.devices,
            type=instance.type,
            architecture=instance.architecture,
            profiles=instance.profiles,
        )
        response = await api.instance_put(name=name, instance=instance_put)
        if response is None or response.status_code != 100:
            self.logger.error(f"Config update of instance '{name}' was not accepted (status_code={response.status_code if response else None})")
            return False
        if not response.operation:
            return False
        return await self._wait_for_operation(response.operation, timeout, f"Config update of instance '{name}'")

    async def attach_network_to_instance(self, name: str, iface_name: str, network: str, timeout: int = 120) -> bool:
        """Attach a NIC device to an existing instance.

        Fetches the current instance, merges the new NIC device into its devices,
        and PUTs the updated instance spec. The instance must be stopped.

        Args:
            name: The instance name.
            iface_name: The interface name inside the instance (e.g. ``"eth1"``).
            network: The managed Incus network to connect the NIC to.
            timeout: Seconds to wait for the update operation to complete.

        Returns:
            ``True`` if the NIC was attached successfully.
        """
        instance = await self.get_istance(name)
        if instance is None:
            return False
        api = pyincusd.InstancesApi(self._incus_client)
        devices = {**(instance.devices or {})}
        devices[iface_name] = {
            "type": "nic",
            "name": iface_name,
            "network": network,
        }
        instance_put = InstancePut(
            config=instance.config,
            devices=devices,
            type=instance.type,
            architecture=instance.architecture,
            profiles=instance.profiles,
        )
        response = await api.instance_put(name=name, instance=instance_put)
        if response is None or response.status_code != 100:
            self.logger.error(f"NIC attach to instance '{name}' was not accepted (status_code={response.status_code if response else None})")
            return False
        if not response.operation:
            return False
        return await self._wait_for_operation(response.operation, timeout, f"NIC attach ({iface_name} -> {network}) on instance '{name}'")

    async def attach_physical_interface_to_instance(self, name: str, iface_name: str, parent_iface: str, timeout: int = 120) -> bool:
        """Attach a physical host NIC device to an existing instance.

        Fetches the current instance, merges the new NIC device into its devices,
        and PUTs the updated instance spec. The instance must be stopped.

        Args:
            name: The instance name.
            iface_name: The interface name inside the instance (e.g. ``"eth1"``).
            parent_iface: The host physical interface to pass through (e.g. ``"usb0"``).
            timeout: Seconds to wait for the update operation to complete.

        Returns:
            ``True`` if the NIC was attached successfully.
        """
        instance = await self.get_istance(name)
        if instance is None:
            return False
        api = pyincusd.InstancesApi(self._incus_client)
        devices = {**(instance.devices or {})}
        devices[iface_name] = {
            "type": "nic",
            "name": iface_name,
            "nictype": "physical",
            "parent": parent_iface,
        }
        instance_put = InstancePut(
            config=instance.config,
            devices=devices,
            type=instance.type,
            architecture=instance.architecture,
            profiles=instance.profiles,
        )
        response = await api.instance_put(name=name, instance=instance_put)
        if response is None or response.status_code != 100:
            self.logger.error(f"Physical NIC attach to instance '{name}' was not accepted (status_code={response.status_code if response else None})")
            return False
        if not response.operation:
            return False
        return await self._wait_for_operation(response.operation, timeout, f"Physical NIC attach ({iface_name} -> {parent_iface}) on instance '{name}'")

    async def detach_network_from_instance(self, name: str, iface_name: str, timeout: int = 120) -> bool:
        """Remove a NIC device from an existing instance.

        Fetches the current instance, removes the device, and PUTs the updated
        instance spec. The instance must be stopped.

        Args:
            name: The instance name.
            iface_name: The device name to remove (e.g. ``"eth1"``).
            timeout: Seconds to wait for the update operation to complete.

        Returns:
            ``True`` if the NIC was removed successfully.
        """
        instance = await self.get_istance(name)
        if instance is None:
            return False
        api = pyincusd.InstancesApi(self._incus_client)
        devices = {**(instance.devices or {})}
        if iface_name not in devices:
            return False
        del devices[iface_name]
        instance_put = InstancePut(
            config=instance.config,
            devices=devices,
            type=instance.type,
            architecture=instance.architecture,
            profiles=instance.profiles,
        )
        response = await api.instance_put(name=name, instance=instance_put)
        if response is None or response.status_code != 100:
            self.logger.error(f"NIC detach from instance '{name}' was not accepted (status_code={response.status_code if response else None})")
            return False
        if not response.operation:
            return False
        return await self._wait_for_operation(response.operation, timeout, f"NIC detach ({iface_name}) from instance '{name}'")

    async def _wait_for_operation(self, operation_url: str, timeout: int, context: str) -> bool:
        """Wait for an Incus async operation to complete.

        Args:
            operation_url: The operation URL returned by the API (e.g.
                ``/1.0/operations/<uuid>``).
            timeout: Seconds to wait for the operation to complete.
            context: Description of the operation, used in error logs.

        Returns:
            ``True`` if the operation completed successfully.
        """
        operation_id = operation_url.rstrip("/").split("/operations/")[-1]
        operations_api = pyincusd.OperationsApi(self._incus_client)
        self.logger.info(f"{context}: waiting for operation '{operation_id}' to complete (timeout={timeout}s)...")
        start_time = time.time()
        try:
            final = await operations_api.operation_wait_get(id=operation_id, timeout=timeout)
        except pyincusd.ApiException as e:
            self.logger.error(f"{context} failed while waiting for operation '{operation_id}': {e}")
            return False

        elapsed = time.time() - start_time
        metadata = final.metadata if final else None
        if metadata and metadata.status_code and metadata.status_code >= 400:
            self.logger.error(f"{context} failed after {elapsed:.1f}s (operation '{operation_id}'): {metadata.err or metadata.status}")
            return False
        self.logger.info(f"{context}: operation '{operation_id}' completed successfully in {elapsed:.1f}s (status='{metadata.status if metadata else 'unknown'}')")
        return True

    async def create_container(self, name: str, image_name: str, container_spec: IncusContainerSpec, start: bool = True, timeout: int = 300) -> Instance | None:
        """Create a container instance from an image alias and wait for creation to complete.

        Serializes the provided :class:`IncusContainerSpec` (config and devices)
        into the flat dicts Incus expects, issues the create request and waits
        for the create operation to finish.

        Args:
            name: Name for the new container.
            image_name: Alias of the source image.
            container_spec: The container specification (config + devices).
            start: Whether to start the container right after creation.
            timeout: Seconds to wait for the create operation to complete.

        Returns:
            The created instance metadata, or ``None`` if the image is missing
            or the creation failed.
        """
        container_spec = container_spec or IncusContainerSpec()
        image = await self.get_image_by_name(name=image_name)
        if not image:
            return None
        api = pyincusd.InstancesApi(self._incus_client)
        container_config = container_spec.config.to_incus_dict() if container_spec.config else {}
        container_devices = {dev_name: dev.to_incus_dict() for dev_name, dev in container_spec.devices.items()} if container_spec.devices else {}
        instance_spec = InstancesPost(
            name=name,
            type="container",
            start=start,
            config=container_config,
            devices=container_devices,
            source=InstanceSource(
                type="image",
                fingerprint=image.fingerprint,
            ),
        )
        result = await api.instances_post(instance=instance_spec)
        if result is None or result.status_code != 100 or not result.operation:
            self.logger.error(f"Creation of container '{name}' was not accepted (status_code={result.status_code if result else None})")
            return None
        if not await self._wait_for_operation(result.operation, timeout, f"Creation of container '{name}'"):
            return None
        return await self.get_istance(name=name)

    async def create_vm(self, name: str, image_name: str, vm_spec: IncusVmSpec, start: bool = True, timeout: int = 300) -> Instance | None:
        """Create a virtual machine instance from an image alias and wait for creation to complete.

        Serializes the provided :class:`IncusVmSpec` (config and devices) into
        the flat dicts Incus expects, issues the create request and waits for
        the create operation to finish.

        Args:
            name: Name for the new VM.
            image_name: Alias of the source (VM-capable) image.
            vm_spec: The VM specification (config + devices).
            start: Whether to start the VM right after creation.
            timeout: Seconds to wait for the create operation to complete.

        Returns:
            The created instance metadata, or ``None`` if the image is missing
            or the creation failed.
        """
        vm_spec = vm_spec or IncusVmSpec()
        image = await self.get_image_by_name(name=image_name)
        if not image:
            return None
        api = pyincusd.InstancesApi(self._incus_client)
        vm_config = vm_spec.config.to_incus_dict() if vm_spec.config else {}
        vm_devices = {dev_name: dev.to_incus_dict() for dev_name, dev in vm_spec.devices.items()} if vm_spec.devices else {}
        instance_spec = InstancesPost(
            name=name,
            type="virtual-machine",
            start=start,
            config=vm_config,
            devices=vm_devices,
            source=InstanceSource(
                type="image",
                fingerprint=image.fingerprint,
            ),
        )
        result = await api.instances_post(instance=instance_spec)
        if result is None or result.status_code != 100 or not result.operation:
            self.logger.error(f"Creation of VM '{name}' was not accepted (status_code={result.status_code if result else None})")
            return None
        if not await self._wait_for_operation(result.operation, timeout, f"Creation of VM '{name}'"):
            return None
        return await self.get_istance(name=name)

    async def _delete_instance(self, name: str, timeout: int = 120) -> bool:
        """Delete an instance, stopping it first if it is running, and wait for the deletion to complete.

        Args:
            name: The instance name to delete.
            timeout: Seconds to wait for the delete operation to complete.

        Returns:
            ``True`` if the delete operation completed successfully,
            ``False`` if the instance could not be stopped first.
        """
        instance = await self.get_istance(name)
        if instance is None:
            return False
        if instance.status.upper() == "RUNNING":
            stopped = await self.stop_instance(name=name)
            if not stopped:
                return False
        api = pyincusd.InstancesApi(self._incus_client)
        result = await api.instance_delete(name=name)
        if result is None or result.status_code != 100:
            self.logger.error(f"Deletion of instance '{name}' was not accepted (status_code={result.status_code if result else None})")
            return False
        if not result.operation:
            return False
        return await self._wait_for_operation(result.operation, timeout, f"Deletion of instance '{name}'")

    async def delete_vm(self, name: str) -> bool:
        return await self._delete_instance(name=name)

    async def delete_container(self, name: str) -> bool:
        return await self._delete_instance(name=name)

    async def _change_instance_state(self, name: str, action: str, force: bool = False, timeout: int = 120) -> bool:
        """Request an instance state change and wait for the operation to complete.

        Args:
            name: The instance name.
            action: The state change action (``start``, ``stop``, ``restart``).
            force: Whether to force the state change.
            timeout: Seconds to wait for the operation to complete.

        Returns:
            ``True`` if the state change operation completed successfully.
        """
        api = pyincusd.InstancesApi(self._incus_client)
        result = await api.instance_state_put(name=name, state=InstanceStatePut(action=action, force=force))
        if result is None or result.status_code != 100:
            self.logger.error(f"State change '{action}' on instance '{name}' was not accepted (status_code={result.status_code if result else None})")
            return False

        if not result.operation:
            return False

        return await self._wait_for_operation(result.operation, timeout, f"State change '{action}' on instance '{name}'")

    async def start_instance(self, name: str, force=False, timeout: int = 120) -> bool:
        """Start an instance and wait for the start operation to complete.

        Args:
            name: The instance name to start.
            force: Whether to force the state change.
            timeout: Seconds to wait for the operation to complete.

        Returns:
            ``True`` if the start operation completed successfully.
        """
        return await self._change_instance_state(name=name, action="start", force=force, timeout=timeout)

    async def stop_instance(self, name: str, force=False, timeout: int = 120) -> bool:
        """Stop an instance and wait for the stop operation to complete.

        Args:
            name: The instance name to stop.
            force: Whether to force the state change.
            timeout: Seconds to wait for the operation to complete.

        Returns:
            ``True`` if the stop operation completed successfully.
        """
        return await self._change_instance_state(name=name, action="stop", force=force, timeout=timeout)

    async def restart_instance(self, name: str, force=False, timeout: int = 120) -> bool:
        """Restart an instance and wait for the restart operation to complete.

        Args:
            name: The instance name to restart.
            force: Whether to force the state change (e.g. hard reset if the
                instance does not shut down cleanly).
            timeout: Seconds to wait for the operation to complete.

        Returns:
            ``True`` if the restart operation completed successfully.
        """
        return await self._change_instance_state(name=name, action="restart", force=force, timeout=timeout)

    async def exec_command(self, name: str, command: List[str], timeout: int = 120) -> str | None:
        """Execute a command inside an instance and return stdout+stderr.

        Uses the Incus ``exec`` endpoint in ``record-output`` mode so that the
        output is captured and can be fetched after the command completes.

        Args:
            name: The instance name.
            command: The command and its arguments as a list (e.g.
                ``["sh", "-c", "cloud-init status --wait"]``).
            timeout: Seconds to wait for the operation to complete.

        Returns:
            The combined output, or ``None`` on failure.
        """
        api = pyincusd.InstancesApi(self._incus_client)

        exec_req = InstanceExecPost(command=command, record_output=True)
        result = await api.instance_exec_post(name=name, var_exec=exec_req)
        if result is None or result.status_code != 100:
            self.logger.error(f"Exec on instance '{name}' was not accepted (status_code={result.status_code if result else None})")
            return None

        if not result.operation:
            return None

        if not await self._wait_for_operation(result.operation, timeout, f"Exec on instance '{name}'"):
            return None

        outputs = await api.instance_exec_outputs_get(name=name)
        if not outputs or not outputs.metadata:
            return ""

        output_parts = []
        for url in outputs.metadata:
            filename = url.rstrip("/").split("/")[-1]
            try:
                content = await api.instance_exec_output_get(name=name, filename=filename)
                if content:
                    output_parts.append(str(content))
            except pyincusd.ApiException as e:
                self.logger.warning(f"Failed to read exec output file {filename}: {e}")

        return "\n".join(output_parts)

    async def list_networks(self) -> List[StrictStr]:
        """List all networks defined on the Incus server.

        Returns:
            The networks metadata (list of network URLs), or an empty list.
        """
        api = pyincusd.NetworksApi(self._incus_client)
        networks = await api.networks_get()
        if not networks or not networks.metadata:
            return []
        return [url.split("/networks/")[-1] for url in networks.metadata]

    async def get_network(self, name: str) -> Network | None:
        """Fetch a single network by name.

        Args:
            name: The network name to look up.

        Returns:
            The :class:`Network` metadata, or ``None`` if it does not exist.
        """
        api = pyincusd.NetworksApi(self._incus_client)
        try:
            network = await api.network_get(name=name)
        except pyincusd.ApiException:
            return None
        return network.metadata if network else None

    async def add_network(self, name: str, network_type: IncusNetworkType, config: Optional[IncusNetworkConfig] = None, description: Optional[str] = None) -> bool:
        """Create a new network on the Incus server.

        If the provided config does not specify any IPv6 address, IPv6 is
        explicitly disabled (``ipv6.address=none``) to prevent Incus from
        auto-assigning a random IPv6 subnet.

        Args:
            name: Name of the network to create (e.g. ``"mybr0"``).
            network_type: Network type (see :class:`IncusNetworkType`).
            config: Optional typed :class:`IncusNetworkConfig`.
            description: Optional human-readable description.

        Returns:
            ``True`` if the network was created (HTTP 200 or 201).
        """
        config = config or IncusNetworkConfig()
        # Disable IPv6 unless the caller explicitly configured an address, so
        # Incus does not auto-assign a random IPv6 ULA subnet.
        if config.ipv6_address is None:
            config.set_ipv6(address="none")
        api = pyincusd.NetworksApi(self._incus_client)
        network_spec = NetworksPost(
            name=name,
            type=IncusNetworkType(network_type).value,
            config=config.to_incus_dict(),
            description=description,
        )
        response = await api.networks_post_with_http_info(network=network_spec)
        return response.status_code in (200, 201)

    async def delete_network(self, name: str) -> bool:
        """Delete a network from the Incus server.

        Args:
            name: Name of the network to delete.

        Returns:
            ``True`` if the network was deleted (status code 200).
        """
        api = pyincusd.NetworksApi(self._incus_client)
        response = await api.network_delete_with_http_info(name=name)
        return response.status_code == 200

    def close(self):
        """Clean up temporary TLS files and close the underlying API client.

        Removes the temporary cert/key/CA files created in :meth:`connect_incus`
        and closes the async ``pyincusd`` client (scheduling the coroutine on the
        running loop if there is one, otherwise running it synchronously).
        """
        if self.closed:
            return
        for temp_path in (self.crt_path, self.key_path, self.ca_path):
            if temp_path:
                temp_path.unlink(missing_ok=True)
        if self._incus_client:
            try:
                asyncio.get_running_loop()
                loop = asyncio.get_event_loop()
                loop.create_task(self._incus_client.close())
            except RuntimeError:
                try:
                    asyncio.run(self._incus_client.close())
                except RuntimeError:
                    pass
        super().close()
