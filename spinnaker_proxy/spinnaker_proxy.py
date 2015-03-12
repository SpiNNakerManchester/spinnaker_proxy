#!/usr/bin/env python

"""A simple port-changing UDP relay proxy."""

import sys

import socket

from select import select

from six import iteritems

import logging

import argparse


class Destination(object):

    def __init__(self, sock, address=None):
        self.sock = sock
        self.address = address


def proxy(port_map, bufsize=4096):
    """A simple port-changing UDP relay proxy.
    
    Parameters
    ----------
    port_map : {external_port: (internal_host, internal_port), ...}
        Proxy requests arriving at localhost:external_port to
        internal_host:internal_port. Proxy requests coming in the opposite
        direction to the most recent sender to external_port.
    bufsize : int
        The buffer to hold UDP packets in. Must be large enough to handle the
        largest UDP packets proxied.
    """
    # A map {socket: Destination, ...} destination to forward any received data
    # to.
    ext_map = {}
    int_map = {}
    
    for external_port, (internal_host, internal_port) in iteritems(port_map):
        ext_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ext_socket.bind(('', external_port))
        
        int_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        int_socket.connect((internal_host, internal_port))
        
        int_map[int_socket] = Destination(ext_socket, None)
        ext_map[ext_socket] = Destination(int_socket,
                                          (internal_host, internal_port))
    
    while True:
        readers, writers, errs = select(list(ext_map) + list(int_map),
                                        [], [])
        for sock in readers:
            # Forward packets coming from external sources
            if sock in ext_map:
                # Receive the datagram
                data, address = sock.recvfrom(bufsize)
                
                # Record the source of this datagram so that any packets
                # returning from the supplied destination are forwarded here.
                destination = ext_map[sock]
                response_destination = int_map[destination.sock]
                if response_destination.address != address:
                    logging.info(
                        "New external {} now connected to internal {}.".format(
                            address, destination.address))
                    response_destination.address = address
                
                # Forward the datagram to the internal endpoint
                destination.sock.send(data)
            
            # Forward packets coming from internal sources
            if sock in int_map:
                # Recieve the datagram
                data = sock.recv(bufsize)
                
                # Find the external address last used to communicate with this
                # internal device
                destination = int_map[sock]
                if destination.address is None:
                    logging.warning("Dropped packet sent from internal "
                                    "before any externals connected.")
                    continue
                
                # Forward to that address
                destination.sock.sendto(data, destination.address)


if __name__=="__main__":
    parser = argparse.ArgumentParser(
        description="Set up a proxy to a locally connected SpiNNaker board.")
    
    parser.add_argument("board", type=str,
                        help="target SpiNNaker board hostname")
    parser.add_argument("bmp", type=str, nargs="?", default=None,
                        help="target BMP hostname")
    parser.add_argument("--scp-port", type=int, default=17893,
                        help="port number to forward SpiNNaker SDP packets to")
    parser.add_argument("--bmp-scp-port", type=int, default=17893,
                        help="port number to forward BMP SDP packets to")
    parser.add_argument("--boot-port", type=int, default=54321,
                        help="port number to forward SpiNNaker boot packets "
                             "to")
    
    parser.add_argument("--external-scp-port", type=int, default=17894,
                        help="port number to accept incoming SpiNNaker SCP "
                             "packets on")
    parser.add_argument("--external-bmp-scp-port", type=int, default=17895,
                        help="port number to accept incoming BMP SCP "
                             "packets on")
    parser.add_argument("--external-boot-port", type=int, default=17896,
                        help="port number to accept incoming SpiNNaker boot "
                             "packets on")
    
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="don't print the connection log")
    
    args = parser.parse_args()
    
    if not args.quiet:
        logging.basicConfig(level=logging.INFO)
    
    port_map = {
        args.external_scp_port: (args.board, args.scp_port),
        args.external_boot_port: (args.board, args.boot_port),
    }
    
    if args.bmp is not None:
        port_map[args.external_bmp_scp_port] = (args.bmp, args.bmp_scp_port)
    
    proxy(port_map)
