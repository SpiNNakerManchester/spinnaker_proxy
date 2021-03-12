#!/usr/bin/env python

# Copyright (c) 2015-2017 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" A proxy for SpiNNaker boards.
"""

import argparse
import logging
import select
import threading

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


def run_proxies(datagram_proxies, event=None):
    """ Run a given set of proxy servers.

    :param ~typing.Iterable(DatagramProxy) datagram_proxies:
        The proxies to run.
    :param event: A way to ask the event processing loop to shut down.
        Set the event and things will stop within a second.
        If not provided, will loop indefinitely.
    :type event: ~threading.Event or None
    """
    if not event:
        event = threading.Event()
        event.clear()
    try:
        while not event.is_set():
            # Find out which sockets to select on
            select_handlers = {}
            for p in datagram_proxies:
                select_handlers.update(p.get_select_handlers())
            fds = list(s for s in select_handlers if s and s.fileno() >= 0)

            # Nothing to do, so stop
            if not fds:
                break

            # Wait for data to arrive on any socket
            readers, _writers, errs = select.select(fds, [], fds, 0.5)

            # Handle the data
            for sock in set(readers + errs):
                select_handlers[sock]()
    finally:
        for p in datagram_proxies:
            p.close()


def _parse_arguments(args=None):
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

    return parser.parse_args(args=args)


def _construct_proxies(args):
    if args.server:
        sdp_proxy = TCPtoUDP if args.sdp_via_tcp else UDPtoUDP
        yield sdp_proxy(args.scp_tunnel_port, (args.target, args.scp_port))

        boot_proxy = TCPtoUDP if args.boot_via_tcp else UDPtoUDP
        yield boot_proxy(args.boot_tunnel_port, (args.target, args.boot_port))
    elif args.client:
        sdp_proxy = UDPtoTCP if args.sdp_via_tcp else UDPtoUDP
        yield sdp_proxy(args.scp_port, (args.target, args.scp_tunnel_port))

        boot_proxy = UDPtoTCP if args.boot_via_tcp else UDPtoUDP
        yield boot_proxy(args.boot_port, (args.target, args.boot_tunnel_port))


def _main_program():
    """ The main program. Assumes that it is only ever called from this file.
    """
    args = _parse_arguments()

    if not args.quiet:
        logging.basicConfig(level=logging.INFO)

    datagram_proxies = list(_construct_proxies(args))

    run_proxies(datagram_proxies)


if __name__ == "__main__":
    _main_program()
