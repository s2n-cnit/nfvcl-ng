import json
import shlex
from typing import Optional, List

from nfvcl_common.utils.api_utils import ApiRequestType


def generate_curl_command(method: ApiRequestType, url: str, payload: Optional[dict] = None, http2prio: bool = True, as_list: bool = False) -> List[str] | str:
    parts = ["curl"]

    if http2prio:
        parts.append("\'--http2-prior-knowledge\'")

    parts.append("\'-s\' \'-o\' \'/dev/null\' \'-w\' \'%{http_code}\'")
    parts.append(f"-X \'{method.value}\' \'{url}\'")

    if payload:
        json_payload = json.dumps(payload, separators=(",", ":"))
        parts.append("-H \'Content-Type: application/json\'")
        parts.append(f"-d '{json_payload}'")

    command = " ".join(parts)

    if as_list:
        return shlex.split(command, posix=True)
    return command
