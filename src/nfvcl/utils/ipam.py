import ipaddress
import socket
from typing import Union, List

from nfvcl.models.network.network_models import IPv4Pool


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


def check_range_in_cidr(ip_min: Union[ipaddress.IPv4Address, str], ip_max: Union[ipaddress.IPv4Address, str], cidr: Union[ipaddress.IPv4Network, str]) -> bool:
    """
    Checks if the IP range <ip_min> and <ip_max> is contained in the CIDR range.

    Args:
        ip_min: The lower IP of the range
        ip_max: The higher IP of the range
        cidr: CIDR

    Returns:
        True if the range is contained in CIDR.
    """
    if type(cidr) is str:
        cidr = ipaddress.IPv4Network(cidr)
    if type(ip_min) is str:
        ip_min = ipaddress.IPv4Address(ip_min)
    if type(ip_max) is str:
        ip_max = ipaddress.IPv4Address(ip_max)
    return ip_min in cidr and ip_max in cidr

def check_ipv4_valid(ipv4: str) -> bool:
    """
    Check if the IPv4 is a valid address
    Args:
        ipv4: The IP (string) to be checked

    Returns:
        True if it is a valid IPv4 address.
    """
    try:
        ipv4_model = ipaddress.IPv4Address(ipv4)
        return True
    except ipaddress.AddressValueError:
        return False

def get_available_network_ip(cidr: ipaddress.IPv4Network, reserved_ranges: List[IPv4Pool]) -> List[IPv4Pool]:
    """
    Returns all the available intervals in a network, given the reserved ranges.
    Args:
        cidr: The CIDR of the network (e.g. '192.168.0.0/16')
        reserved_ranges: The ranges that must NOT be used

    Returns:
        Available IPv4 ranges of the network.
    """
    # cidr[1] applied on a IPv4Network return the 2nd adress of the cidr.
    # Starting from [4] (.3) because .1 and .2 (DHCP) should be used by OpenStack.
    # Ending [-2] (.254) because .255 is broadcast.
    available_ranges: List[IPv4Pool] = [IPv4Pool(start=cidr[4], end=cidr[-2])]

    # Ordering IP addresses
    ordered_reserved_ranges = sorted(reserved_ranges, key=lambda k: socket.inet_aton(k.start.exploded))

    for reserved_range in ordered_reserved_ranges:
        if type(reserved_range.start) is str:
            reserved_range.start = ipaddress.IPv4Address(reserved_range.start)
        if type(reserved_range.end) is str:
            reserved_range.end = ipaddress.IPv4Address(reserved_range.end)
        if int(reserved_range.end) - int(reserved_range.start) < 0:
            raise ValueError("Reserved range [{}-{}] is not valid -> Starting address comes before ending address.".
                             format(reserved_range.start, reserved_range.end))

        if not check_range_in_cidr(reserved_range.start, reserved_range.end, cidr):
            raise ValueError("Range {}-{} not in cidr {}".format(reserved_range.start, reserved_range.end, cidr))

        for ava_range in available_ranges:
            # If the available range is ending after the start of the reservation there could be space for a range
            if ava_range.end > reserved_range.start:
                # Moving the end of the available range to the start of reservation range and saving the old end.
                original_end = ava_range.end
                ava_range.end = reserved_range.start - 1

                # If the actual ava_range is not more valid let's delete it (means that 2 reservation are adjacent)
                if ava_range.end <= ava_range.start:
                    available_ranges.remove(ava_range)

                # Add new available range
                available_ranges.append(IPv4Pool(start=reserved_range.end + 1, end=original_end))
                # Stopping the inner FOR
                break
    return available_ranges


def get_range_length(ip_min: ipaddress.IPv4Address, ip_max: ipaddress.IPv4Address) -> int:
    """
    Returns the number of IP address in a range.
    Args:
        ip_min: The starting IP of the range
        ip_max: The ending IP of the range

    Returns: the number of IP address in the range.
    """
    return int(ip_max) - int(ip_min)


def get_range_in_cidr(cidr: ipaddress.IPv4Network, reserved_ranges: List[IPv4Pool],
                      range_length: int) -> IPv4Pool:
    """
    Return a free interval of sequential IP addresses in the network.
    Args:
        cidr: The CIDR of the network (e.g. 192.168.0.0/16)
        reserved_ranges: The already reserved ranges in the network
        range_length: The length of sequential interval

    Returns:
        The free interval that can be allocated.
    """
    available_ranges = get_available_network_ip(cidr, reserved_ranges)
    for ava_range in available_ranges:
        if get_range_length(ava_range.start, ava_range.end) >= range_length:
            # Found a range that is available and len enough
            # Reducing to the required number of IPs
            ava_range.end = ava_range.start+range_length
            return ava_range

    raise ValueError('Not possible to get a range in the network cidr')
