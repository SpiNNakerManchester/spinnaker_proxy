#!/usr/bin/env python

""" A proxy for SpiNNaker boards.
"""

import argparse
import logging
from select import select

from .proxies import TCPtoUDP, UDPtoTCP, UDPtoUDP


SCP_PORT = 17893
""" Port used for SCP communications.
"""

SCP_TUNNEL_PORT = 17894
""" Port used for tunnelling SCP communications.
"""

BOOT_PORT = 54321
""" Port used to boot a SpiNNaker machine.
"""

BOOT_TUNNEL_PORT = 17895
""" Port used for tunnelling boot packets.
"""


def run_proxies(datagram_proxies):
    """ Run a given set of proxy servers indefinitely.

    :type datagram_proxies: iterable(:py:class:`DatagramProxy`)
    """
    while True:
        # Find out which sockets to select on
        select_handlers = {}
        for p in datagram_proxies:
            select_handlers.update(p.get_select_handlers())

        # Wait for data to arrive on any socket
        readers, _writers, _errs = select(list(select_handlers), [], [])

        # Handle the data
        for sock in readers:
            select_handlers[sock]()


def _main_program():
    """ The main program. Assumes that it is only ever called from this file.
    """
    parser = argparse.ArgumentParser(
        description="A 'tunnel' proxy for connecting to remote SpiNNaker "
        "boards.")

    parser.add_argument("target", type=str,
                        help="target hostname (i.e. SpiNNaker board or "
                        "another proxy)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--server", action="store_true",
                       help="act as a proxy server (target should be a "
                       "SpiNNaker machine)")
    group.add_argument("-c", "--client", action="store_true",
                       help="connect to a proxy server")

    parser.add_argument("-t", "--boot-via-tcp", action="store_true",
                        help="tunnel boot packets via a TCP connection")

    parser.add_argument("-T", "--sdp-via-tcp", action="store_true",
                        help="tunnel SDP packets via a TCP connection")

    parser.add_argument("--scp-port", type=int, default=SCP_PORT,
                        help="SCP port number used by SpiNNaker boards")
    parser.add_argument("--boot-port", type=int, default=BOOT_PORT,
                        help="Port number used to boot SpiNNaker boards")
    parser.add_argument("--scp-tunnel-port", type=int,
                        default=SCP_TUNNEL_PORT,
                        help="Port number for tunnelling SCP data")
    parser.add_argument("--boot-tunnel-port", type=int,
                        default=BOOT_TUNNEL_PORT,
                        help="Port number for tunnelling boot data")

    parser.add_argument("-q", "--quiet", action="store_true",
                        help="don't print the connection log")

    args = parser.parse_args()

    if not args.quiet:
        logging.basicConfig(level=logging.INFO)

    datagram_proxies = []

    if args.server:
        sdp_proxy = TCPtoUDP if args.sdp_via_tcp else UDPtoUDP
        datagram_proxies.append(
            sdp_proxy(args.scp_tunnel_port, (args.target, args.scp_port)))

        boot_proxy = TCPtoUDP if args.boot_via_tcp else UDPtoUDP
        datagram_proxies.append(
            boot_proxy(args.boot_tunnel_port, (args.target, args.boot_port)))
    elif args.client:
        sdp_proxy = UDPtoTCP if args.sdp_via_tcp else UDPtoUDP
        datagram_proxies.append(
            sdp_proxy(args.scp_port, (args.target, args.scp_tunnel_port)))

        boot_proxy = UDPtoTCP if args.boot_via_tcp else UDPtoUDP
        datagram_proxies.append(
            boot_proxy(args.boot_port, (args.target, args.boot_tunnel_port)))

    try:
        run_proxies(datagram_proxies)
    finally:
        for p in datagram_proxies:
            p.close()


if __name__ == "__main__":
    _main_program()
