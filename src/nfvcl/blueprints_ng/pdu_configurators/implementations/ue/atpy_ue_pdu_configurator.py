import time
from contextlib import contextmanager
from typing import List, Generator, Dict, Optional

from atpy_client import ATPyClient
from atpy_client.models import DeviceModel, Cops, CopsModeEnum, OperatorFormatEnum, Cgdcont, PDPType, PdpState, UsbNetMode
from pydantic import Field

from nfvcl.blueprints_ng.pdu_configurators.types.ue_pdu_configurator import GenericUEConfigurator
from nfvcl_common.ansible_builder import AnsiblePlaybookBuilder
from nfvcl_common.ansible_utils import run_ansible_playbook
from nfvcl_common.base_model import NFVCLBaseModel
from nfvcl_common.utils.blue_utils import rel_path
from nfvcl_common.utils.log import create_logger
from nfvcl_core_models.network.network_models import PduModel
from nfvcl_core_models.pdu.ue import UEPDUConfigure
from nfvcl_core_models.resources import PDUResourceAnsibleConfiguration

logger = create_logger('ATPYPDUConfigurator')

MODEM = {
    "quectel": "2c7c"
}


class CleanupVars(NFVCLBaseModel):
    container_name: str = Field()


class ConfigVars(CleanupVars):
    vendor_id: str = Field()
    vendor_name: str = Field()


class ExperimentVars(NFVCLBaseModel):
    container_name: str = Field()
    container_image_name: str = Field()
    tcpdump: bool = Field()
    modem_interface: str = Field()
    modem_interfce_ip: str = Field()
    modem_interfce_mac: str = Field()
    env_vars: Dict[str, str] = Field(default_factory=dict)


class NetDiscoverAnsibleConfigurator(PDUResourceAnsibleConfiguration):
    vars: ConfigVars

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook NetDiscoverConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("discover_net_interface_playbook.yaml"))
        ansible_builder.set_vars_from_fields(self.vars)
        return ansible_builder.build()


class ExperimentAnsible(PDUResourceAnsibleConfiguration):
    vars: ExperimentVars

    def dump_playbook(self) -> str:
        ansible_builder = AnsiblePlaybookBuilder("Playbook ExperimentAnsibleConfigurator")
        ansible_builder.add_tasks_from_file(rel_path("experiment_playbook.yaml"))
        ansible_builder.set_vars_from_fields(self.vars)
        return ansible_builder.build()


class AtpyUePDUConfigurator(GenericUEConfigurator):

    def __init__(self, pdu_model: PduModel):
        super().__init__(pdu_model)

    @contextmanager
    def _get_client(self) -> Generator[ATPyClient, None, None]:
        with ATPyClient(base_url=f"http://{self.pdu_model.get_mgmt_ip()}:8000", timeout=120) as client:
            available_devices: List[DeviceModel] = client.ports.get_at_ports()
            if len(available_devices) == 0:
                raise Exception("No ports available")
            for device in available_devices:
                if device.manufacturer.upper() == self.pdu_model.config["modem_type"].upper():
                    client.connect(device.port[0])
                    break
            else:
                raise Exception(f"No modem {self.pdu_model.config['modem_type']} found on {self.pdu_model.get_mgmt_ip()}")
            yield client

    def _wait_network_registration(self, client, gsm: bool = False, twog_threeg: bool = False, fourg: bool = False, fiveg: bool = False):
        logger.info("Waiting for network registration")
        timeout = 300
        start_time = time.time()
        desired = {
            "GSM": gsm,
            "2G3G": twog_threeg,
            "4G": fourg,
            "5G": fiveg,
        }
        field_map = {
            "GSM": "gsm_umts",
            "2G3G": "gprs_edge",
            "4G": "lte",
            "5G": "five_g",
        }
        while time.time() - start_time < timeout:
            try:
                report = client.network.get_registration()
            except Exception:
                logger.warning("Failed to get network registration, retrying...")
                time.sleep(5)
                continue
            all_registered = True
            for label, wanted in desired.items():
                if not wanted:
                    continue
                net_status = getattr(report, field_map[label])
                if net_status is None or net_status.status.value not in (1, 5):
                    all_registered = False
                    logger.info(f"Network {label} still not registered")
                    break
            if all_registered:
                logger.info("Network registration complete")
                break
            time.sleep(5)
        else:
            raise Exception("Timeout exceeded: NOT registered after 1 minute")

    def configure(self, config: UEPDUConfigure):
        logger.info(f"Configuring UE PDU {self.pdu_model.name} with {config}")

        with self._get_client() as client:

            logger.info(f"Factory resetting modem")
            client.device.factory_reset()

            logger.info(f"Setting pdp context")
            client.pdp.set_context(Cgdcont(cid=1, apn=config.dnn, pdptype=PDPType.IP))

            logger.info(f"Setting operator to {config.plmn}")
            client.network.set_operator(Cops(mode=CopsModeEnum.AUTOMATIC, format=OperatorFormatEnum.GSM, numeric=config.plmn))

            usbmode = client.network.get_usbnet()
            if usbmode.mode.value != UsbNetMode.ECM:
                logger.info(f"Setting USB mode to ECM")
                client.network.set_usbnet(mode=UsbNetMode.ECM)
                logger.info(f"Restarting modem")
                client.device.restart()

            self._wait_network_registration(client, fiveg=True)

            contexts_status = client.pdp.get_contexts_status()
            for context in contexts_status:
                if context.cid == 1 and context.state == PdpState.DEACTIVATED:
                    logger.info(f"Activating pdp context {context.cid}")
                    client.pdp.activate(context_id=1)
                    break

            nat_status = client.device.get_nat_status()
            if nat_status["nat_enabled"]:
                logger.info(f"Disabling NAT")
                client.device.disable_nat()

            config_vars: ConfigVars = ConfigVars(
                container_name=self.pdu_model.name,
                vendor_id=MODEM[self.pdu_model.config["modem_type"].lower()],
                vendor_name=self.pdu_model.config["modem_type"].upper()
            )

            _, collected_facts = run_ansible_playbook(
                host=self.pdu_model.get_mgmt_ip(),
                username=self.pdu_model.username,
                password=self.pdu_model.password,
                become_password=self.pdu_model.become_password,
                playbook=NetDiscoverAnsibleConfigurator(vars=config_vars).dump_playbook()
            )

            iface = collected_facts.get("net_interface_name")
            return iface

    def cleanup(self):
        with self._get_client() as client:
            logger.info(f"Factory resetting modem")
            client.device.factory_reset()

    def run_experiment(self, container_name: str, container_image_name: str, tcpdump: bool, container_iface: str, modem_ip: str, iface_mac: str, env_vars: Optional[Dict[str, str]] = None):
        if env_vars is None:
            env_vars = {}
        experiment_vars = ExperimentVars(
            container_name=container_name,
            container_image_name=container_image_name,
            tcpdump=tcpdump,
            modem_interface=container_iface,
            modem_interfce_ip=modem_ip,
            modem_interfce_mac=iface_mac,
            env_vars=env_vars,
        )
        run_ansible_playbook(
            host=self.pdu_model.get_mgmt_ip(),
            username=self.pdu_model.username,
            password=self.pdu_model.password,
            become_password=self.pdu_model.become_password,
            playbook=ExperimentAnsible(vars=experiment_vars).dump_playbook()
        )
