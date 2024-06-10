from typing import Optional, List


def create_ansible_inventory(host: str, username: str, password: str, become_password: Optional[str] = None):
    str_list: List[str] = [f"ansible_host='{host}'", f"ansible_user='{username}'", f"ansible_password='{password}'"]

    if become_password:
        str_list.append(f"ansible_become_pass='{become_password}'")

    str_list.append("ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'")

    return f"{host} {' '.join(str_list)}"


