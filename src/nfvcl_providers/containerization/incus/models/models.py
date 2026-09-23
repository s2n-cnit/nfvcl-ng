"""Pydantic models and enums describing Incus resources used by the NFVCL Incus provider.

These models provide a typed, validated way to build the ``config`` and
``devices`` dictionaries that the Incus REST API (via ``pyincusd``) expects.

Incus represents instance configuration as a flat ``dict[str, str]`` where the
keys are dotted strings (e.g. ``"limits.cpu"``) and every value is a string.
The models here expose Pythonic snake_case field names, keep the real Incus key
as the pydantic ``alias``, and provide ``to_incus_dict()`` / ``to_incus_value()``
helpers that render everything back into the exact string form Incus wants.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import ConfigDict, Field

from nfvcl_common.base_model import NFVCLBaseModel


class IncusArchitecture(str, Enum):
    """Architecture identifiers accepted by Incus (used in image metadata)."""
    I686 = "i686"
    X86_64 = "x86_64"
    ARMV6L = "armv6l"
    ARMV7L = "armv7l"
    ARMV8L = "armv8l"
    AARCH64 = "aarch64"
    PPC = "ppc"
    PPC64 = "ppc64"
    PPC64LE = "ppc64le"
    S390X = "s390x"
    MIPS = "mips"
    MIPS64 = "mips64"
    RISCV32 = "riscv32"
    RISCV64 = "riscv64"
    LOONGARCH64 = "loongarch64"


class IncusOsName(str, Enum):
    """Operating system identifiers commonly used in Incus image metadata."""
    ALMALINUX = "almalinux"
    ALPINE = "alpine"
    ARCHLINUX = "archlinux"
    CENTOS = "centos"
    DEBIAN = "debian"
    FEDORA = "fedora"
    KALI = "kali"
    OPENSUSE = "opensuse"
    ORACLE = "oracle"
    ROCKYLINUX = "rockylinux"
    UBUNTU = "ubuntu"
    VOID = "void"


class IncusUbuntuRelease(str, Enum):
    """Ubuntu release codenames (used as the ``release`` image property)."""
    BIONIC = "bionic"
    FOCAL = "focal"
    JAMMY = "jammy"
    NOBLE = "noble"


class IncusImageType(str, Enum):
    """Type of an Incus instance/image: system container or virtual machine."""
    CONTAINER = "container"
    VIRTUAL_MACHINE = "virtual-machine"


class IncusNetworkType(str, Enum):
    """Network types supported by Incus (refer to Incus docs/networks)."""
    BRIDGE = "bridge"
    OVN = "ovn"
    MACVLAN = "macvlan"
    SRIOV = "sriov"
    PHYSICAL = "physical"


class IncusByteUnit(str, Enum):
    """Byte-size units accepted by Incus.

    Decimal units (kB, MB, ...) are powers of 1000, binary units (KiB, MiB, ...)
    are powers of 1024.
    """
    KB = "kB"
    MB = "MB"
    GB = "GB"
    TB = "TB"
    KIB = "KiB"
    MIB = "MiB"
    GIB = "GiB"
    TIB = "TiB"


class IncusByteSize(NFVCLBaseModel):
    """A byte quantity expressed as a numeric value plus an Incus unit.

    Incus expects sizes as a single string such as ``"2GiB"``; this model keeps
    the value and unit separate and renders that string via :meth:`to_incus_value`.

    Attributes:
        value: The numeric magnitude of the size.
        unit: The unit the magnitude is expressed in (defaults to GiB).
    """
    value: int
    unit: IncusByteUnit = IncusByteUnit.GIB

    def to_incus_value(self) -> str:
        """Render the size as the Incus string form (e.g. ``"2GiB"``)."""
        # NFVCLBaseModel uses use_enum_values=True, so `unit` may already be a
        # plain string; handle both the enum and the raw string case.
        unit = self.unit.value if isinstance(self.unit, IncusByteUnit) else str(self.unit)
        return f"{self.value}{unit}"


class IncusIpRange(NFVCLBaseModel):
    """An inclusive IP range expressed as a start and end address.

    Incus expects a range as the single string ``"START-END"`` (used for
    ``ipv4.dhcp.ranges`` / ``ipv6.dhcp.ranges``); this model keeps the two
    endpoints separate and renders that string via :meth:`to_incus_value`.

    Attributes:
        start: First address of the range (inclusive).
        end: Last address of the range (inclusive).
    """
    start: str
    end: str

    def to_incus_value(self) -> str:
        """Render the range as the Incus string form (e.g. ``"10.0.0.100-10.0.0.200"``)."""
        return f"{self.start}-{self.end}"


def _to_incus_value(value) -> str:
    """Convert a single Python value to the string form Incus expects.

    Rules:
        - Objects exposing ``to_incus_value()`` (e.g. :class:`IncusByteSize`,
          :class:`IncusIpRange`) are rendered through that method.
        - Lists/tuples are rendered element-by-element and joined with ``,``
          (e.g. a list of :class:`IncusIpRange` becomes ``"r1,r2"``).
        - Booleans become the strings ``"true"`` / ``"false"``.
        - Enums are rendered as their ``.value``.
        - Everything else is passed through ``str()``.
    """
    if hasattr(value, "to_incus_value"):
        return value.to_incus_value()
    if isinstance(value, (list, tuple)):
        return ",".join(_to_incus_value(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _incus_serialize(model: NFVCLBaseModel) -> dict:
    """Dump a pydantic model to the flat ``dict[str, str]`` Incus expects.

    Iterates over the declared model fields (using each field's alias as the
    real Incus key), skips ``None`` values, and converts each value with
    :func:`_to_incus_value`. Any ``extra`` keys allowed by the model (e.g.
    ``user.*`` namespaces) are appended as-is.

    Args:
        model: The model instance to serialize.

    Returns:
        A dictionary mapping Incus keys to their string values.
    """
    result: dict = {}
    # Typed fields: use the field alias (the actual Incus key) when present.
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        if value is None:
            continue
        result[field.alias or name] = _to_incus_value(value)
    # Extra (untyped) keys allowed via extra="allow".
    for key, value in (model.model_extra or {}).items():
        if value is not None:
            result[key] = _to_incus_value(value)
    return result


class IncusVmConfig(NFVCLBaseModel):
    """Typed representation of the ``config`` dict for an Incus virtual machine.

    Only the most common VM-applicable keys are typed. Because the model uses
    ``extra="allow"``, any other Incus key (including the open namespaces such as
    ``user.*``, ``environment.*``, ``image.*``, ``raw.*``) can still be set and
    will be serialized. Snake_case field names map to the real dotted Incus keys
    via their aliases.

    Use :meth:`to_incus_dict` to produce the dict accepted by the Incus API, or
    the ``set_*`` helper methods to build the config fluently.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # Resource limits
    limits_cpu: Optional[int] = Field(default=None, alias="limits.cpu")
    limits_cpu_pin_strategy: Optional[str] = Field(default=None, alias="limits.cpu.pin_strategy")
    limits_memory: Optional[IncusByteSize] = Field(default=None, alias="limits.memory")
    limits_memory_hugepages: Optional[bool] = Field(default=None, alias="limits.memory.hugepages")
    limits_disk_priority: Optional[int] = Field(default=None, alias="limits.disk.priority")

    # Security (VM specific)
    security_secureboot: Optional[bool] = Field(default=None, alias="security.secureboot")
    security_sev: Optional[bool] = Field(default=None, alias="security.sev")
    security_sev_policy_es: Optional[bool] = Field(default=None, alias="security.sev.policy.es")
    security_csm: Optional[bool] = Field(default=None, alias="security.csm")
    security_protection_delete: Optional[bool] = Field(default=None, alias="security.protection.delete")

    # Agent / cloud-init
    agent_nic_config: Optional[bool] = Field(default=None, alias="agent.nic_config")
    cloud_init_user_data: Optional[str] = Field(default=None, alias="cloud-init.user-data")
    cloud_init_vendor_data: Optional[str] = Field(default=None, alias="cloud-init.vendor-data")
    cloud_init_network_config: Optional[str] = Field(default=None, alias="cloud-init.network-config")

    # Boot
    boot_autostart: Optional[bool] = Field(default=None, alias="boot.autostart")
    boot_autostart_delay: Optional[int] = Field(default=None, alias="boot.autostart.delay")
    boot_autostart_priority: Optional[int] = Field(default=None, alias="boot.autostart.priority")
    boot_host_shutdown_timeout: Optional[int] = Field(default=None, alias="boot.host_shutdown_timeout")
    boot_stop_priority: Optional[int] = Field(default=None, alias="boot.stop.priority")

    # Migration / snapshots / raw
    migration_stateful: Optional[bool] = Field(default=None, alias="migration.stateful")
    snapshots_schedule: Optional[str] = Field(default=None, alias="snapshots.schedule")
    raw_qemu: Optional[str] = Field(default=None, alias="raw.qemu")
    raw_qemu_conf: Optional[str] = Field(default=None, alias="raw.qemu.conf")

    def to_incus_dict(self) -> dict:
        """Serialize this config into the flat string dict Incus expects."""
        return _incus_serialize(self)

    @classmethod
    def empty(cls) -> IncusVmConfig:
        """Return an empty config (all keys unset), ready to be built fluently."""
        return cls()

    def set_cpu_limit(self, cpu: int, pin_strategy: Optional[str] = None) -> IncusVmConfig:
        """Set the CPU limit (``limits.cpu``) and, optionally, the pin strategy.

        Args:
            cpu: Number of vCPUs to expose to the VM.
            pin_strategy: Optional value for ``limits.cpu.pin_strategy``.

        Returns:
            ``self`` to allow method chaining.
        """
        self.limits_cpu = cpu
        if pin_strategy is not None:
            self.limits_cpu_pin_strategy = pin_strategy
        return self

    def set_memory_limit(self, memory: IncusByteSize, hugepages: Optional[bool] = None) -> IncusVmConfig:
        """Set the memory limit (``limits.memory``) and, optionally, hugepages.

        Args:
            memory: Amount of RAM as an :class:`IncusByteSize`.
            hugepages: Optional value for ``limits.memory.hugepages``.

        Returns:
            ``self`` to allow method chaining.
        """
        self.limits_memory = memory
        if hugepages is not None:
            self.limits_memory_hugepages = hugepages
        return self

    def set_flags(
        self,
        limits_memory_hugepages: Optional[bool] = None,
        security_secureboot: Optional[bool] = None,
        security_sev: Optional[bool] = None,
        security_sev_policy_es: Optional[bool] = None,
        security_csm: Optional[bool] = None,
        security_protection_delete: Optional[bool] = None,
        agent_nic_config: Optional[bool] = None,
        boot_autostart: Optional[bool] = None,
        migration_stateful: Optional[bool] = None,
    ) -> IncusVmConfig:
        """Set any of the boolean config flags in a single call.

        Only arguments that are explicitly provided (non-None) are applied; the
        others are left untouched.

        Returns:
            ``self`` to allow method chaining.
        """
        for field_name, value in (
            ("limits_memory_hugepages", limits_memory_hugepages),
            ("security_secureboot", security_secureboot),
            ("security_sev", security_sev),
            ("security_sev_policy_es", security_sev_policy_es),
            ("security_csm", security_csm),
            ("security_protection_delete", security_protection_delete),
            ("agent_nic_config", agent_nic_config),
            ("boot_autostart", boot_autostart),
            ("migration_stateful", migration_stateful),
        ):
            if value is not None:
                setattr(self, field_name, value)
        return self

    def set_cloud_init(
        self,
        user_data: Optional[str] = None,
        vendor_data: Optional[str] = None,
        network_config: Optional[str] = None,
    ) -> IncusVmConfig:
        """Set the cloud-init parameters (``cloud-init.*`` keys).

        Only arguments that are explicitly provided (non-None) are applied.

        Args:
            user_data: Content for ``cloud-init.user-data`` (e.g. a #cloud-config document).
            vendor_data: Content for ``cloud-init.vendor-data``.
            network_config: Content for ``cloud-init.network-config``.

        Returns:
            ``self`` to allow method chaining.
        """
        if user_data is not None:
            self.cloud_init_user_data = user_data
        if vendor_data is not None:
            self.cloud_init_vendor_data = vendor_data
        if network_config is not None:
            self.cloud_init_network_config = network_config
        return self


class IncusVmDevice(NFVCLBaseModel):
    """Base class for an Incus VM device entry.

    A device in Incus is a ``dict[str, str]`` with at least a ``type`` key.
    Subclasses add the typed keys for a specific device type; ``extra="allow"``
    lets any additional/unmodeled key be supplied.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str

    def to_incus_dict(self) -> dict:
        """Serialize this device into the flat string dict Incus expects."""
        return _incus_serialize(self)


class IncusVmDiskDevice(IncusVmDevice):
    """A ``disk`` device (root disk or an extra volume) attached to a VM.

    Attributes:
        path: Mount path inside the instance (``/`` for the root disk).
        source: Source of the disk (e.g. a volume name or host path).
        pool: Storage pool that backs the disk.
        size: Disk size as an :class:`IncusByteSize`.
        read_only: Whether the disk is mounted read-only (``readonly`` key).
        boot_priority: Boot order priority (``boot.priority`` key).
    """
    type: str = "disk"
    path: Optional[str] = None
    source: Optional[str] = None
    pool: Optional[str] = None
    size: Optional[IncusByteSize] = None
    read_only: Optional[bool] = Field(default=None, alias="readonly")
    boot_priority: Optional[int] = Field(default=None, alias="boot.priority")


class IncusVmNicDevice(IncusVmDevice):
    """A ``nic`` (network interface) device attached to a VM.

    Attributes:
        network: Managed network to connect to.
        name: Interface name inside the instance.
        nictype: NIC type (e.g. ``bridged``, ``macvlan``) when not using ``network``.
        parent: Parent host interface/bridge (used with ``nictype``).
        hwaddr: MAC address to assign.
        ipv4_address: Static IPv4 address (``ipv4.address`` key).
        ipv6_address: Static IPv6 address (``ipv6.address`` key).
        boot_priority: Boot order priority (``boot.priority`` key).
    """
    type: str = "nic"
    network: Optional[str] = None
    name: Optional[str] = None
    nictype: Optional[str] = None
    parent: Optional[str] = None
    hwaddr: Optional[str] = None
    ipv4_address: Optional[str] = Field(default=None, alias="ipv4.address")
    ipv6_address: Optional[str] = Field(default=None, alias="ipv6.address")
    boot_priority: Optional[int] = Field(default=None, alias="boot.priority")


class IncusVmGpuDevice(IncusVmDevice):
    """A ``gpu`` device passed through to a VM.

    Attributes:
        gputype: GPU passthrough type (e.g. ``physical``, ``mdev``, ``mig``).
        pci: PCI address of the GPU to expose.
        id: Card identifier used to select the GPU.
    """
    type: str = "gpu"
    gputype: Optional[str] = None
    pci: Optional[str] = None
    id: Optional[str] = None


class IncusVmDevicePassthrough(IncusVmDevice):
    """A PCI passthrough device for a VM.

    Attributes:
        address: PCI address of the device to pass through.
    """
    type: str = "pci"
    address: Optional[str] = None


class IncusVmSpec(NFVCLBaseModel):
    """Full specification used to create an Incus virtual machine.

    Bundles the instance ``config`` and ``devices`` into a single object that
    the provider serializes when building the create request.

    Attributes:
        config: Optional typed VM configuration.
        devices: Optional mapping of device name -> device model.
    """
    config: Optional[IncusVmConfig] = None
    devices: Optional[dict[str, IncusVmDevice]] = None

    def add_device(self, name: str, device: IncusVmDevice) -> IncusVmSpec:
        """Add (or replace) a device in the spec under the given name.

        Creates the ``devices`` mapping if it does not exist yet.

        Args:
            name: Device name/key (e.g. ``"root"``, ``"eth0"``).
            device: The device model to store.

        Returns:
            ``self`` to allow method chaining.
        """
        if self.devices is None:
            self.devices = {}
        self.devices[name] = device
        return self

    def add_disk_device(self, name: str, device: IncusVmDiskDevice) -> IncusVmSpec:
        """Add a disk device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)

    def add_nic_device(self, name: str, device: IncusVmNicDevice) -> IncusVmSpec:
        """Add a nic device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)

    def add_gpu_device(self, name: str, device: IncusVmGpuDevice) -> IncusVmSpec:
        """Add a gpu device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)

    def add_passthrough_device(self, name: str, device: IncusVmDevicePassthrough) -> IncusVmSpec:
        """Add a pci passthrough device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)


class IncusContainerConfig(NFVCLBaseModel):
    """Typed representation of the ``config`` dict for an Incus system container.

    Only the most common container-applicable keys are typed. Because the model
    uses ``extra="allow"``, any other Incus key (including the open namespaces
    such as ``user.*``, ``environment.*``, ``image.*``, ``raw.*``) can still be
    set and will be serialized. Snake_case field names map to the real dotted
    Incus keys via their aliases.

    Use :meth:`to_incus_dict` to produce the dict accepted by the Incus API, or
    the ``set_*`` helper methods to build the config fluently.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # Resource limits
    limits_cpu: Optional[int] = Field(default=None, alias="limits.cpu")
    limits_cpu_allowance: Optional[str] = Field(default=None, alias="limits.cpu.allowance")
    limits_cpu_priority: Optional[int] = Field(default=None, alias="limits.cpu.priority")
    limits_memory: Optional[IncusByteSize] = Field(default=None, alias="limits.memory")
    limits_memory_enforce: Optional[str] = Field(default=None, alias="limits.memory.enforce")
    limits_memory_swap: Optional[bool] = Field(default=None, alias="limits.memory.swap")
    limits_disk_priority: Optional[int] = Field(default=None, alias="limits.disk.priority")
    limits_processes: Optional[int] = Field(default=None, alias="limits.processes")

    # Security (container specific)
    security_nesting: Optional[bool] = Field(default=None, alias="security.nesting")
    security_privileged: Optional[bool] = Field(default=None, alias="security.privileged")
    security_protection_delete: Optional[bool] = Field(default=None, alias="security.protection.delete")
    security_protection_shift: Optional[bool] = Field(default=None, alias="security.protection.shift")
    security_idmap_isolated: Optional[bool] = Field(default=None, alias="security.idmap.isolated")
    security_idmap_size: Optional[int] = Field(default=None, alias="security.idmap.size")
    security_syscalls_intercept_mknod: Optional[bool] = Field(default=None, alias="security.syscalls.intercept.mknod")
    security_syscalls_intercept_setxattr: Optional[bool] = Field(default=None, alias="security.syscalls.intercept.setxattr")

    # Cloud-init
    cloud_init_user_data: Optional[str] = Field(default=None, alias="cloud-init.user-data")
    cloud_init_vendor_data: Optional[str] = Field(default=None, alias="cloud-init.vendor-data")
    cloud_init_network_config: Optional[str] = Field(default=None, alias="cloud-init.network-config")

    # Boot
    boot_autostart: Optional[bool] = Field(default=None, alias="boot.autostart")
    boot_autostart_delay: Optional[int] = Field(default=None, alias="boot.autostart.delay")
    boot_autostart_priority: Optional[int] = Field(default=None, alias="boot.autostart.priority")
    boot_host_shutdown_timeout: Optional[int] = Field(default=None, alias="boot.host_shutdown_timeout")
    boot_stop_priority: Optional[int] = Field(default=None, alias="boot.stop.priority")

    # Snapshots / raw
    snapshots_schedule: Optional[str] = Field(default=None, alias="snapshots.schedule")
    raw_lxc: Optional[str] = Field(default=None, alias="raw.lxc")

    def to_incus_dict(self) -> dict:
        """Serialize this config into the flat string dict Incus expects."""
        return _incus_serialize(self)

    @classmethod
    def empty(cls) -> IncusContainerConfig:
        """Return an empty config (all keys unset), ready to be built fluently."""
        return cls()

    def set_cpu_limit(self, cpu: int, allowance: Optional[str] = None) -> IncusContainerConfig:
        """Set the CPU limit (``limits.cpu``) and, optionally, the allowance.

        Args:
            cpu: Number of vCPUs to expose to the container.
            allowance: Optional value for ``limits.cpu.allowance`` (e.g. ``"50%"``).

        Returns:
            ``self`` to allow method chaining.
        """
        self.limits_cpu = cpu
        if allowance is not None:
            self.limits_cpu_allowance = allowance
        return self

    def set_memory_limit(self, memory: IncusByteSize, swap: Optional[bool] = None) -> IncusContainerConfig:
        """Set the memory limit (``limits.memory``) and, optionally, swap.

        Args:
            memory: Amount of RAM as an :class:`IncusByteSize`.
            swap: Optional value for ``limits.memory.swap``.

        Returns:
            ``self`` to allow method chaining.
        """
        self.limits_memory = memory
        if swap is not None:
            self.limits_memory_swap = swap
        return self

    def set_flags(
        self,
        limits_memory_swap: Optional[bool] = None,
        security_nesting: Optional[bool] = None,
        security_privileged: Optional[bool] = None,
        security_protection_delete: Optional[bool] = None,
        security_protection_shift: Optional[bool] = None,
        security_idmap_isolated: Optional[bool] = None,
        security_syscalls_intercept_mknod: Optional[bool] = None,
        security_syscalls_intercept_setxattr: Optional[bool] = None,
        boot_autostart: Optional[bool] = None,
    ) -> IncusContainerConfig:
        """Set any of the boolean config flags in a single call.

        Only arguments that are explicitly provided (non-None) are applied; the
        others are left untouched.

        Returns:
            ``self`` to allow method chaining.
        """
        for field_name, value in (
            ("limits_memory_swap", limits_memory_swap),
            ("security_nesting", security_nesting),
            ("security_privileged", security_privileged),
            ("security_protection_delete", security_protection_delete),
            ("security_protection_shift", security_protection_shift),
            ("security_idmap_isolated", security_idmap_isolated),
            ("security_syscalls_intercept_mknod", security_syscalls_intercept_mknod),
            ("security_syscalls_intercept_setxattr", security_syscalls_intercept_setxattr),
            ("boot_autostart", boot_autostart),
        ):
            if value is not None:
                setattr(self, field_name, value)
        return self

    def set_cloud_init(
        self,
        user_data: Optional[str] = None,
        vendor_data: Optional[str] = None,
        network_config: Optional[str] = None,
    ) -> IncusContainerConfig:
        """Set the cloud-init parameters (``cloud-init.*`` keys).

        Only arguments that are explicitly provided (non-None) are applied.

        Args:
            user_data: Content for ``cloud-init.user-data`` (e.g. a #cloud-config document).
            vendor_data: Content for ``cloud-init.vendor-data``.
            network_config: Content for ``cloud-init.network-config``.

        Returns:
            ``self`` to allow method chaining.
        """
        if user_data is not None:
            self.cloud_init_user_data = user_data
        if vendor_data is not None:
            self.cloud_init_vendor_data = vendor_data
        if network_config is not None:
            self.cloud_init_network_config = network_config
        return self


class IncusContainerDevice(NFVCLBaseModel):
    """Base class for an Incus container device entry.

    A device in Incus is a ``dict[str, str]`` with at least a ``type`` key.
    Subclasses add the typed keys for a specific device type; ``extra="allow"``
    lets any additional/unmodeled key be supplied.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    type: str

    def to_incus_dict(self) -> dict:
        """Serialize this device into the flat string dict Incus expects."""
        return _incus_serialize(self)


class IncusContainerDiskDevice(IncusContainerDevice):
    """A ``disk`` device (root disk or a bind-mount) attached to a container.

    Attributes:
        path: Mount path inside the instance (``/`` for the root disk).
        source: Source of the disk (a storage volume, or a host path for a bind-mount).
        pool: Storage pool that backs the disk.
        size: Disk size as an :class:`IncusByteSize`.
        read_only: Whether the disk is mounted read-only (``readonly`` key).
    """
    type: str = "disk"
    path: Optional[str] = None
    source: Optional[str] = None
    pool: Optional[str] = None
    size: Optional[IncusByteSize] = None
    read_only: Optional[bool] = Field(default=None, alias="readonly")


class IncusContainerNicDevice(IncusContainerDevice):
    """A ``nic`` (network interface) device attached to a container.

    Attributes:
        network: Managed network to connect to.
        name: Interface name inside the instance.
        nictype: NIC type (e.g. ``bridged``, ``macvlan``) when not using ``network``.
        parent: Parent host interface/bridge (used with ``nictype``).
        hwaddr: MAC address to assign.
        ipv4_address: Static IPv4 address (``ipv4.address`` key).
        ipv6_address: Static IPv6 address (``ipv6.address`` key).
    """
    type: str = "nic"
    network: Optional[str] = None
    name: Optional[str] = None
    nictype: Optional[str] = None
    parent: Optional[str] = None
    hwaddr: Optional[str] = None
    ipv4_address: Optional[str] = Field(default=None, alias="ipv4.address")
    ipv6_address: Optional[str] = Field(default=None, alias="ipv6.address")


class IncusContainerGpuDevice(IncusContainerDevice):
    """A ``gpu`` device exposed to a container.

    Attributes:
        gputype: GPU type (e.g. ``physical``, ``mdev``).
        pci: PCI address of the GPU to expose.
        id: Card identifier used to select the GPU.
    """
    type: str = "gpu"
    gputype: Optional[str] = None
    pci: Optional[str] = None
    id: Optional[str] = None


class IncusContainerSpec(NFVCLBaseModel):
    """Full specification used to create an Incus system container.

    Bundles the instance ``config`` and ``devices`` into a single object that
    the provider serializes when building the create request.

    Attributes:
        config: Optional typed container configuration.
        devices: Optional mapping of device name -> device model.
    """
    config: Optional[IncusContainerConfig] = None
    devices: Optional[dict[str, IncusContainerDevice]] = None

    def add_device(self, name: str, device: IncusContainerDevice) -> IncusContainerSpec:
        """Add (or replace) a device in the spec under the given name.

        Creates the ``devices`` mapping if it does not exist yet.

        Args:
            name: Device name/key (e.g. ``"root"``, ``"eth0"``).
            device: The device model to store.

        Returns:
            ``self`` to allow method chaining.
        """
        if self.devices is None:
            self.devices = {}
        self.devices[name] = device
        return self

    def add_disk_device(self, name: str, device: IncusContainerDiskDevice) -> IncusContainerSpec:
        """Add a disk device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)

    def add_nic_device(self, name: str, device: IncusContainerNicDevice) -> IncusContainerSpec:
        """Add a nic device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)

    def add_gpu_device(self, name: str, device: IncusContainerGpuDevice) -> IncusContainerSpec:
        """Add a gpu device to the spec. Returns ``self`` for chaining."""
        return self.add_device(name, device)


class IncusNetworkConfig(NFVCLBaseModel):
    """Typed representation of the ``config`` dict for an Incus network.

    Only the most common keys (mainly for bridge/ovn networks) are typed.
    Because the model uses ``extra="allow"``, any other Incus network key can
    still be set and will be serialized. Snake_case field names map to the real
    dotted Incus keys via their aliases.

    Use :meth:`to_incus_dict` to produce the dict accepted by the Incus API, or
    the ``set_*`` helper methods to build the config fluently.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # IPv4
    ipv4_address: Optional[str] = Field(default=None, alias="ipv4.address")
    ipv4_nat: Optional[bool] = Field(default=None, alias="ipv4.nat")
    ipv4_dhcp: Optional[bool] = Field(default=None, alias="ipv4.dhcp")
    ipv4_dhcp_ranges: Optional[List[IncusIpRange]] = Field(default=None, alias="ipv4.dhcp.ranges")
    ipv4_routes: Optional[str] = Field(default=None, alias="ipv4.routes")
    ipv4_routing: Optional[bool] = Field(default=None, alias="ipv4.routing")

    # IPv6
    ipv6_address: Optional[str] = Field(default=None, alias="ipv6.address")
    ipv6_nat: Optional[bool] = Field(default=None, alias="ipv6.nat")
    ipv6_dhcp: Optional[bool] = Field(default=None, alias="ipv6.dhcp")
    ipv6_dhcp_ranges: Optional[List[IncusIpRange]] = Field(default=None, alias="ipv6.dhcp.ranges")
    ipv6_routes: Optional[str] = Field(default=None, alias="ipv6.routes")
    ipv6_routing: Optional[bool] = Field(default=None, alias="ipv6.routing")

    # DNS
    dns_domain: Optional[str] = Field(default=None, alias="dns.domain")
    dns_mode: Optional[str] = Field(default=None, alias="dns.mode")
    dns_nameservers: Optional[str] = Field(default=None, alias="dns.nameservers")

    # Bridge
    bridge_driver: Optional[str] = Field(default=None, alias="bridge.driver")
    bridge_external_interfaces: Optional[str] = Field(default=None, alias="bridge.external_interfaces")
    bridge_mtu: Optional[int] = Field(default=None, alias="bridge.mtu")
    bridge_hwaddr: Optional[str] = Field(default=None, alias="bridge.hwaddr")

    def to_incus_dict(self) -> dict:
        """Serialize this config into the flat string dict Incus expects."""
        return _incus_serialize(self)

    @classmethod
    def empty(cls) -> IncusNetworkConfig:
        """Return an empty config (all keys unset), ready to be built fluently."""
        return cls()

    def set_ipv4(
        self,
        address: Optional[str] = None,
        nat: Optional[bool] = None,
        dhcp: Optional[bool] = None,
        dhcp_ranges: Optional[List[IncusIpRange]] = None,
    ) -> IncusNetworkConfig:
        """Set the IPv4 parameters. Only provided (non-None) values are applied.

        Args:
            address: CIDR address for the network (``ipv4.address``), or ``"none"``/``"auto"``.
            nat: Whether to NAT the IPv4 traffic (``ipv4.nat``).
            dhcp: Whether to enable IPv4 DHCP (``ipv4.dhcp``).
            dhcp_ranges: DHCP ranges as a list of :class:`IncusIpRange`
                (``ipv4.dhcp.ranges``); rendered as a comma-separated
                ``START-END`` list.

        Returns:
            ``self`` to allow method chaining.
        """
        if address is not None:
            self.ipv4_address = address
        if nat is not None:
            self.ipv4_nat = nat
        if dhcp is not None:
            self.ipv4_dhcp = dhcp
        if dhcp_ranges is not None:
            self.ipv4_dhcp_ranges = dhcp_ranges
        return self

    def set_ipv6(
        self,
        address: Optional[str] = None,
        nat: Optional[bool] = None,
        dhcp: Optional[bool] = None,
        dhcp_ranges: Optional[List[IncusIpRange]] = None,
    ) -> IncusNetworkConfig:
        """Set the IPv6 parameters. Only provided (non-None) values are applied.

        Args:
            address: CIDR address for the network (``ipv6.address``), or ``"none"``/``"auto"``.
            nat: Whether to NAT the IPv6 traffic (``ipv6.nat``).
            dhcp: Whether to enable IPv6 DHCP (``ipv6.dhcp``).
            dhcp_ranges: DHCP ranges as a list of :class:`IncusIpRange`
                (``ipv6.dhcp.ranges``); rendered as a comma-separated
                ``START-END`` list.

        Returns:
            ``self`` to allow method chaining.
        """
        if address is not None:
            self.ipv6_address = address
        if nat is not None:
            self.ipv6_nat = nat
        if dhcp is not None:
            self.ipv6_dhcp = dhcp
        if dhcp_ranges is not None:
            self.ipv6_dhcp_ranges = dhcp_ranges
        return self

    def set_dns(
        self,
        domain: Optional[str] = None,
        mode: Optional[str] = None,
        nameservers: Optional[str] = None,
    ) -> IncusNetworkConfig:
        """Set the DNS parameters. Only provided (non-None) values are applied.

        Args:
            domain: DNS domain (``dns.domain``).
            mode: DNS mode (``dns.mode``, e.g. ``managed``, ``dynamic``, ``none``).
            nameservers: DNS nameservers (``dns.nameservers``).

        Returns:
            ``self`` to allow method chaining.
        """
        if domain is not None:
            self.dns_domain = domain
        if mode is not None:
            self.dns_mode = mode
        if nameservers is not None:
            self.dns_nameservers = nameservers
        return self
