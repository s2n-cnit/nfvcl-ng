import json
import shlex
from typing import List, Optional

from nfvcl_common.utils.api_utils import HttpRequestType


def generate_curl_command(
    method: HttpRequestType,
    url: str,
    payload: Optional[dict] = None,
    http2prio: bool = True,
    as_list: bool = False,
    include_response_body: bool = False,
    connect_timeout: Optional[int] = None,
    max_time: Optional[int] = None,
) -> List[str] | str:
    parts = ["curl"]

    if http2prio:
        parts.append("'--http2-prior-knowledge'")

    if connect_timeout is not None:
        parts.append(f"'--connect-timeout' '{connect_timeout}'")
    if max_time is not None:
        parts.append(f"'--max-time' '{max_time}'")

    if include_response_body:
        parts.append("'-sS' '-w' '\\n%{http_code}'")
    else:
        # Keep the historical output contract: discard the response body and
        # emit only the HTTP status code.
        parts.append("'-s' '-o' '/dev/null' '-w' '%{http_code}'")
    parts.append(f"-X '{method.value}' '{url}'")

    if payload:
        json_payload = json.dumps(payload, separators=(",", ":"))
        parts.append("-H 'Content-Type: application/json'")
        parts.append(f"-d '{json_payload}'")

    command = " ".join(parts)

    if as_list:
        return shlex.split(command, posix=True)
    return command


def parse_curl_response(response: str) -> tuple[str, int]:
    """Parse output produced with ``include_response_body=True``."""
    body, separator, status_code = response.rpartition("\n")
    if not separator:
        raise ValueError("Curl response does not contain an HTTP status code")

    try:
        return body, int(status_code.strip())
    except ValueError as error:
        raise ValueError(f"Invalid HTTP status code in curl response: {status_code!r}") from error
