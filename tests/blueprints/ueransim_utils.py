import re
import time
from typing import Optional

from nfvcl_core.utils.blue_utils import get_yaml_parser
from utils import SSH


class UeransimSSH(SSH):
    def __init__(self, ip, user=None, passwd=None):
        super().__init__(ip, user, passwd)

    def check_gnb_connection(self):
        timeout = time.time() + 60 * 1
        while True:
            stdout = self.execute_ssh_command("journalctl -u ueransim-gnb.service -b", sudo=True)
            output = ' '.join(stdout.readlines())
            output = re.search("successful", output).group()
            if output == "successful" or time.time() > timeout:
                return output == "successful"

    def restart_ue_service(self, imsi):
        self.execute_ssh_command(f"systemctl restart ueransim-ue-sim-{imsi}.service", sudo=True)

    def run_command_with_nr_cli(self, imsi: str, command: str) -> dict:
        stdout = "\n".join(self.execute_ssh_command(f"/opt/UERANSIM/nr-cli imsi-{imsi} -e '{command}'", sudo=False).readlines()).strip()
        return get_yaml_parser().load(stdout)

    def get_interface_by_ip(self, ip: str) -> Optional[str]:
        stdout = self.execute_ssh_command("ip -br -4 a sh | grep " + ip + " | awk '{print $1}'")
        output = stdout.readline().strip()
        if len(output) == 0:
            return None
        return output

    def wait_for_active_pdu_session(self, imsi, timeout = 10):
        counter = 0
        while counter < timeout:
            ps_list = self.run_command_with_nr_cli(imsi, "ps-list")
            if ps_list and "PDU Session1" in ps_list:
                if ps_list["PDU Session1"]["state"] == "PS-ACTIVE":
                    return
            time.sleep(1)
            counter += 1
        raise Exception("PDU Session not active, reached timeout")

    def get_ue_tun_name(self, imsi) -> str:
        self.wait_for_active_pdu_session(imsi)
        ip = self.run_command_with_nr_cli(imsi, "ps-list")["PDU Session1"]["address"]
        return self.get_interface_by_ip(ip)

    def check_ue_registered(self, imsi: str, timeout = 10) -> bool:
        counter = 0
        while counter < timeout:
            ue_status = self.run_command_with_nr_cli(imsi, "status")
            if ue_status["cm-state"] == "CM-CONNECTED" and ue_status["rm-state"] == "RM-REGISTERED" and ue_status["mm-state"] == "MM-REGISTERED/NORMAL-SERVICE":
                return True
            time.sleep(1)
            counter += 1
        return False


    def check_ue_connectivity(self, imsi: str, destination: str) -> bool:
        interface = self.get_ue_tun_name(imsi)
        timeout = time.time() + 10 * 1
        while True:
            stdout = self.execute_ssh_command(f"ping -c 1 -I {interface} {destination} > /dev/null ;  echo $?")
            output = stdout.readline().strip()
            if output == "0" or time.time() > timeout:
                return output == "0"

# ue_ssh = UeransimSSH("192.168.254.16")
# ue_ssh.restart_ue_service("001014000000001")
# aa = ue_ssh.check_ue_registered("001014000000001")
# print(aa)
# aa = ue_ssh.check_ue_connectivity("001014000000001", "1.1.1.1")
# print(aa)
# aa = ue_ssh.check_ue_connectivity("001014000000002", "1.1.1.1")
# print(aa)
