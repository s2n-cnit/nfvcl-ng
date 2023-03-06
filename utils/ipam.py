import ipaddress
from typing import Union, List


def is_ip_in_range(ip: Union[ipaddress.IPv4Address, str],
                   ip_min: Union[ipaddress.IPv4Address, str],
                   ip_max: Union[ipaddress.IPv4Address, str]) -> bool:

    if type(ip) is str:
        ip = ipaddress.IPv4Address(ip)
    if type(ip_min) is str:
        ip_min = ipaddress.IPv4Address(ip_min)
    if type(ip_max) is str:
        ip_max = ipaddress.IPv4Address(ip_max)

    return ip_min <= ip <= ip_max


def check_range_in_cidr(
        ip_min: Union[ipaddress.IPv4Address, str],
        ip_max: Union[ipaddress.IPv4Address, str],
        cidr: Union[ipaddress.IPv4Network, str]) -> bool:
    if type(cidr) is str:
        cidr = ipaddress.IPv4Network(cidr)
    if type(ip_min) is str:
        ip_min = ipaddress.IPv4Address(ip_min)
    if type(ip_max) is str:
        ip_max = ipaddress.IPv4Address(ip_max)
    return ip_min in cidr and ip_max in cidr


def get_available_network_ip(
        cidr: Union[ipaddress.IPv4Network, str],
        reserved_ranges: List[dict]) -> List[dict]:

    if type(cidr) is str:
        cidr = ipaddress.IPv4Network(cidr)

    available_ranges = [{"start": cidr[1], "end": cidr[-2]}]

    ordered_reserved_ranges = sorted(reserved_ranges, key=lambda k: k['start'])

    for _range in ordered_reserved_ranges:
        if type(_range["start"]) is str:
            _range["start"] = ipaddress.IPv4Address(_range["start"])
        if type(_range["end"]) is str:
            _range["end"] = ipaddress.IPv4Address(_range["end"])

        if not check_range_in_cidr(_range["start"], _range["end"], cidr):
            raise ValueError("Range {}-{} not in cidr {}". format(_range["start"], _range["end"], cidr))

        for a in available_ranges:
            if a['end'] > _range["start"]:
                original_end = a['end']
                a['end'] = _range["start"] - 1
                if _range["end"] >= a['end']:
                    available_ranges.append({"start": _range["end"] + 1, "end": original_end})
                break
    # cast_available_ranges = [{"start": str(r["start"]), "end": str(r["end"])} for r in available_ranges]
    return available_ranges


def get_range_length(
        ip_min: Union[ipaddress.IPv4Address, str],
        ip_max: Union[ipaddress.IPv4Address, str]) -> int:

    if type(ip_min) is str:
        ip_min = ipaddress.IPv4Address(ip_min)
    if type(ip_max) is str:
        ip_max = ipaddress.IPv4Address(ip_max)
    return int(ip_max) - int(ip_min)


def get_range_in_cidr(
        cidr: Union[ipaddress.IPv4Network, str],
        reserved_ranges: List[dict],
        range_length: int) -> dict:

    available_ranges = get_available_network_ip(cidr, reserved_ranges)
    placeholder = None
    for r in available_ranges:
        if get_range_length(r['start'], r['end']) >= range_length:
            placeholder = r['start']
            break
    if placeholder is None:
        raise ValueError('not possible to get a range in the network cidr')
    else:
        return {'start': str(placeholder), 'end': str(placeholder + range_length - 1)}


"""
print(is_ip_in_range("192.168.0.10", "192.168.0.10", "192.168.0.20"))
a = get_available_network_ip("192.168.0.0/24", [{"start": "192.168.0.10", "end": "192.168.0.20"}])

print(a)
for r in a:
    print(get_range_length(r['start'], r['end']))

print(get_range_in_cidr("192.168.0.0/24", [{"start": "192.168.0.10", "end": "192.168.0.20"}], 15))
"""
