#!/usr/bin/env python

"""A proxy for SpiNNaker boards."""

import sys

import socket

import struct

from select import select

from six import iteritems

import logging

import threading

import argparse


SCP_PORT = 17893
"""Port used for SCP communications."""

SCP_TUNNEL_PORT = 17894
"""Port used for tunnelling SCP communications."""

BOOT_PORT = 54321
"""Port used to boot a SpiNNaker machine"""

BOOT_TUNNEL_PORT = 17895
"""Port used for tunnelling boot packets."""


class TCPDatagramProtocol(object):
    """A simple TCP-based protocol for transmitting/receiving datagrams.
    
    The protocol simply sends datagrams down the TCP connection proceeded by a
    32-bit (network-order) unsigned integer which gives the length of the
    datagram (in bytes) that follows.
    """
    
    def __init__(self):
        # Buffer to hold incomplete datagrams received over TCP
        self.buf = b""
    
    def recv(self, tcp_data):
        """Generate packets in incoming TCP data.
        
        Parameters
        ----------
        tcp_data : bytes
            Raw data read from a TCP socket.
        
        Generates
        ---------
        datagram: bytes
            A series of datagrams (possibly none) received from the connection.
        """
        # Accumulate received data
        self.buf += tcp_data
        
        while len(self.buf) >= 4:
            datagram_length = struct.unpack("!I", self.buf[:4])[0]
            if len(self.buf) >= 4 + datagram_length:
                # If a complete datagram has arrived, yield it
                datagram, self.buf = (
                    self.buf[4:4 + datagram_length],
                    self.buf[4 + datagram_length:]
                )
                yield datagram
            else:
                break
    
    def send(self, datagram):
        """Encode a datagram for transmission down a TCP socket.
        
        Parameters
        ----------
        datagram : bytes
            The datagram to encode.
        
        Returns
        ----------
        bytes
            A series of bytes to send down the TCP socket.
        """
        return struct.pack("!I", len(datagram)) + datagram


class DatagramProxy(object):
    """A simple proxy server which transparently forwards datagram-based
    communications."""
    
    def get_select_handlers(self):
        """List the sockets to select on and their on-readable handlers.
        
        Returns
        -------
        {socket: func, ...}
            All sockets should be selected for readabillity, and, when
            readable, func should be called.
        """
        raise NotImplementedError()
    
    
    def close(self):
        """Close all open connections."""
        raise NotImplementedError()


class UDPtoUDP(DatagramProxy):
    """A UDP to UDP proxy.
    
    This proxy listens on an "external" UDP port and awaits the arrival of UDP
    datagrams. These datagrams are transparently forwarded to the "internal" UDP
    address upon arrival. If any UDP datagrams are received back from the internal
    connection, these are forwarded to the most recent external host to send a
    UDP datagram to the external UDP port.
    
    This proxy essentially allows port numbers to be changed.
    """
    
    def __init__(self, ext_udp_port, int_udp_address, bufsize=4096):
        self.bufsize = bufsize
        
        self.ext_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ext_sock.bind(("", ext_udp_port))
        self.ext_address = None
        
        self.int_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.int_sock.connect(int_udp_address)
    
    
    def ext_to_int(self):
        """Forward a UDP datagram arriving from the external socket to the
        internal socket."""
        # Receive the external datagram, recording the originating address of
        # the packet (to allow directing of return packets)
        datagram, ext_address = self.ext_sock.recvfrom(self.bufsize)
        if ext_address != self.ext_address:
            logging.info("New UDP connection from {}".format(ext_address))
            self.ext_address = ext_address
        
        # Forward the datagram to the internal socket
        self.int_sock.send(datagram)
    
    def int_to_ext(self):
        """Forward a UDP datagram arriving from the internal socket to the
        external socket."""
        # Receive the internal datagram
        datagram = self.int_sock.recv(self.bufsize)
        
        # Forward to the external socket at the address most recently received
        # from
        if self.ext_address is not None:
            self.ext_sock.sendto(datagram, self.ext_address)
        else:
            logging.warning(
                "UDPtoUDP: Got UDP data before UDP 'connection' made.")
    
    def get_select_handlers(self):
        return {
            self.ext_sock: self.ext_to_int,
            self.int_sock: self.int_to_ext,
        }
    
    
    def close(self):
        self.ext_sock.close()
        self.int_sock.close()


class UDPtoTCP(DatagramProxy):
    """Forward UDP datagrams over a TCP connection.
    
    This proxy listens on a UDP port and connects to a TCP server. When a UDP
    datagram is received, it is forwarded down the TCP connection. When a
    datagram is received from the TCP connection, a UDP datagram is sent to the
    last address a UDP datagram was received from.
    
    Since TCP is stream-based not datagram-based, each datagram is prefixed with
    a 32-bit number indicating the datagram's length in bytes.
    
    If the TCP connection is closed, this proxy will raise an exception when it
    next attempts to forward a datagram.
    """
    
    def __init__(self, udp_port, tcp_address, bufsize=4096):
        self.bufsize = bufsize
        
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("", udp_port))
        self.udp_address = None
        
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.connect(tcp_address)
        
        self.tcp_protocol = TCPDatagramProtocol()
    
    def udp_to_tcp(self):
        """Forward received UDP datagrams over TCP."""
        # Receive the datagram, recording the originating address of the packet
        # (to allow directing of return packets)
        datagram, udp_address = self.udp_sock.recvfrom(self.bufsize)
        if udp_address != self.udp_address:
            logging.info("New UDP connection from {}".format(udp_address))
            self.udp_address = udp_address
        
        # Forward the datagram over TCP (prepending with the datagram length)
        self.tcp_sock.send(self.tcp_protocol.send(datagram))
    
    def tcp_to_udp(self):
        """Unpack received TCP data and forward any datagrams over UDP."""
        data = self.tcp_sock.recv(self.bufsize)
        assert len(data) > 0, "Remote socket closed prematurely."
        for datagram in self.tcp_protocol.recv(data):
            # Forward the datagram to the last UDP address received from
            if self.udp_address is not None:
                self.udp_sock.sendto(datagram, self.udp_address)
            else:
                logging.warning(
                    "UDPtoTCP: Got TCP data before UDP 'connection' made.")
    
    def get_select_handlers(self):
        return {
            self.udp_sock: self.udp_to_tcp,
            self.tcp_sock: self.tcp_to_udp,
        }
    
    def close(self):
        self.udp_sock.close()
        self.tcp_sock.close()


class TCPtoUDP(DatagramProxy):
    """Unpack datagrams sent over a TCP connection into UDP datagrams.
    
    This proxy sets up a TCP server and 'connects' to a specified UDP address.
    Datagrams sent to the TCP server are forwarded as UDP datagrams to the
    specified destination. UDP datagrams received are forwarded down the TCP
    connection.
    
    Since TCP is stream-based not datagram-based, each datagram is prefixed with
    a 32-bit number indicating the datagram's length in bytes.
    
    When a connection is made to the TCP server, all previous TCP connections
    are closed.
    """
    
    def __init__(self, tcp_port, udp_address, bufsize=4096):
        self.bufsize = bufsize
        
        # The TCP server
        self.tcp_listen_sock = socket.socket(socket.AF_INET,
                                             socket.SOCK_STREAM)
        self.tcp_listen_sock.setsockopt(socket.SOL_SOCKET,
                                        socket.SO_REUSEADDR, 1)
        self.tcp_listen_sock.bind(("", tcp_port))
        self.tcp_listen_sock.listen(1)
        
        # The most recently connected socket to the server (or None if not
        # connected)
        self.tcp_sock = None
        
        self.tcp_protocol = None
        
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.connect(udp_address)
    
    def on_connect(self):
        if self.tcp_sock is not None:
            self.tcp_sock.close()
        
        self.tcp_sock, address = self.tcp_listen_sock.accept()
        self.tcp_protocol = TCPDatagramProtocol()
        logging.info("New TCP connection from {}".format(address))
    
    def udp_to_tcp(self):
        datagram = self.udp_sock.recv(self.bufsize)
        if self.tcp_sock is not None:
            self.tcp_sock.send(self.tcp_protocol.send(datagram))
        else:
            logging.warning(
                "TCPtoUDP: Got UDP data before TCP connection made.")
    
    def tcp_to_udp(self):
        data = self.tcp_sock.recv(self.bufsize)
        if data == "":
            # Socket closed.
            self.tcp_sock.close()
            self.tcp_sock = None
        else:
            for datagram in self.tcp_protocol.recv(data):
                self.udp_sock.send(datagram)
    
    def get_select_handlers(self):
        handlers = {
            self.udp_sock: self.udp_to_tcp,
            self.tcp_listen_sock: self.on_connect,
        }
        
        if self.tcp_sock is not None:
            handlers[self.tcp_sock] = self.tcp_to_udp
        
        return handlers
    
    def close(self):
        self.udp_sock.close()
        self.tcp_listen_sock.close()
        
        if self.tcp_sock is not None:
            self.tcp_sock.close()


def run_proxy(datagram_proxies):
    """Run a given set of proxy servers indefinitely.
    
    Parameters
    ----------
    datagram_proxies : [:py:class:`.DatagramProxy`, ...]
    """
    while True:
        # Find out which sockets to select on
        select_handlers = {}
        for p in datagram_proxies:
            select_handlers.update(p.get_select_handlers())
        
        # Wait for data to arrive on any socket
        readers, writers, errs = select(list(select_handlers), [], [])
        
        # Handle the data
        for sock in readers:
            select_handlers[sock]()


if __name__=="__main__":
    parser = argparse.ArgumentParser(
        description="A 'tunnel' proxy for connecting to remote SpiNNaker boards.")
    
    parser.add_argument("target", type=str,
                        help="target hostname (i.e. SpiNNaker board or another proxy)")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--server", action="store_true",
                       help="act as a proxy server (target should be a SpiNNaker machine)")
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
    parser.add_argument("--scp-tunnel-port", type=int, default=SCP_TUNNEL_PORT,
                        help="Port number for tunnelling SCP data")
    parser.add_argument("--boot-tunnel-port", type=int, default=BOOT_TUNNEL_PORT,
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
        run_proxy(datagram_proxies)
    finally:
        for p in datagram_proxies:
            p.close()
