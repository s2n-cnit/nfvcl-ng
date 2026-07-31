import pytest

from nfvcl_common.utils.api_utils import HttpRequestType
from nfvcl_common.utils.curl_utils import generate_curl_command, parse_curl_response


def test_generate_curl_command_keeps_status_only_output_by_default():
    command = generate_curl_command(
        HttpRequestType.GET,
        "http://example.test/resource",
        as_list=True,
    )

    assert command == [
        "curl",
        "--http2-prior-knowledge",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-X",
        "GET",
        "http://example.test/resource",
    ]


def test_generate_and_parse_curl_command_with_response_body():
    command = generate_curl_command(
        HttpRequestType.GET,
        "http://example.test/resource",
        http2prio=False,
        as_list=True,
        include_response_body=True,
        connect_timeout=3,
        max_time=5,
    )

    assert command == [
        "curl",
        "--connect-timeout",
        "3",
        "--max-time",
        "5",
        "-sS",
        "-w",
        "\\n%{http_code}",
        "-X",
        "GET",
        "http://example.test/resource",
    ]
    assert parse_curl_response('{"ready":true}\n200') == ('{"ready":true}', 200)
    assert parse_curl_response("null\n404") == ("null", 404)


def test_parse_curl_response_rejects_status_only_contract():
    with pytest.raises(ValueError, match="does not contain"):
        parse_curl_response("200")
