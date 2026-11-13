"""Try IPv4 addresses before IPv6 for every connection this process makes.

Some networks hand the device an IPv6 address with no working IPv6 route. Python
connects to each resolved address in turn, waiting a full timeout on each, so
with GitHub's four IPv6 addresses first a request hangs for over a minute before
IPv4 is tried. Sorting IPv4 first keeps IPv6 as the fallback.
"""
import socket

_getaddrinfo = socket.getaddrinfo


def _ipv4_first(*args, **kwargs):
    infos = _getaddrinfo(*args, **kwargs)
    return sorted(infos, key=lambda info: info[0] != socket.AF_INET)


def prefer_ipv4():
    socket.getaddrinfo = _ipv4_first
