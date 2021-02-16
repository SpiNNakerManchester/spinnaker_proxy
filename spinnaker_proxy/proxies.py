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

""" The implementations of the proxy classes.
"""

import logging
import socket

from .support import DatagramProxy, TCPDatagramProtocol

DEFAULT_BUFFER_SIZE = 4096


def udp_socket(bind_port=None, connect_address=None):
    """ How to make a UDP socket.

    :param int bind_port:
        If provided, what local port to send and receive packets via.
    :param tuple(str,int) connect_address:
        If provided, what remote IP address/port to send packets to and
        receive them from.
    :return: The configured socket.
    :rtype: socket.SocketType
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bind_port is not None:
        sock.bind(("", bind_port))
    if connect_address is not None:
        sock.connect(connect_address)
    return sock


def tcp_socket(bind_port=None, connect_address=None):
    """ How to make a TCP socket.

    :param int bind_port:
        If provided, what local port to send and receive data via.
    :param tuple(str,int) connect_address:
        If provided, what remote IP address/port to send data to and
        receive it from.
    :return: The configured socket.
    :rtype: socket.SocketType
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if bind_port is not None:
        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", bind_port))
    if connect_address is not None:
        sock.connect(connect_address)
    return sock


class UDPtoUDP(DatagramProxy):
    """ A UDP to UDP proxy.

    This proxy listens on an "external" UDP port and awaits the arrival of
    UDP datagrams. These datagrams are transparently forwarded to the
    "internal" UDP address upon arrival. If any UDP datagrams are received
    back from the internal connection, these are forwarded to the most recent
    external host to send a UDP datagram to the external UDP port.

    This proxy essentially allows port numbers to be changed.
    """

    def __init__(self, ext_udp_port, int_udp_address,
                 bufsize=DEFAULT_BUFFER_SIZE):
        #: The buffer size (usually 4kB)
        self.bufsize = bufsize

        #: The external socket
        self.ext_sock = udp_socket(bind_port=ext_udp_port)
        #: The address associated with the external socket
        self.ext_address = None

        #: The internal socket
        self.int_sock = udp_socket(connect_address=int_udp_address)

    def ext_to_int(self):
        """ Forward a UDP datagram arriving from the external socket to the\
            internal socket."""
        # Receive the external datagram, recording the originating address of
        # the packet (to allow directing of return packets)
        datagram, ext_address = self.ext_sock.recvfrom(self.bufsize)
        if ext_address != self.ext_address:
            logging.info("new UDP connection from {}".format(ext_address))
            self.ext_address = ext_address

        # Forward the datagram to the internal socket
        self.int_sock.send(datagram)

    def int_to_ext(self):
        """ Forward a UDP datagram arriving from the internal socket to the\
            external socket."""
        # Receive the internal datagram
        datagram = self.int_sock.recv(self.bufsize)

        # Forward to the external socket at the address most recently received
        # from
        if self.ext_address is None:
            logging.warning("got UDP data before UDP 'connection' made")
            return

        self.ext_sock.sendto(datagram, self.ext_address)

    def get_select_handlers(self):
        return {
            self.ext_sock: self.ext_to_int,
            self.int_sock: self.int_to_ext,
        }

    def close(self):
        self.ext_sock.close()
        self.int_sock.close()


class UDPtoTCP(DatagramProxy):
    """ Forward UDP datagrams over a TCP connection.

    This proxy listens on a UDP port and connects to a TCP server. When a UDP
    datagram is received, it is forwarded down the TCP connection. When a
    datagram is received from the TCP connection, a UDP datagram is sent to
    the last address a UDP datagram was received from.

    Since TCP is stream-based not datagram-based, each datagram is prefixed
    with a 32-bit number indicating the datagram's length in bytes.

    If the TCP connection is closed, this proxy will raise an exception when
    it next attempts to forward a datagram.
    """

    def __init__(self, udp_port, tcp_address,
                 bufsize=DEFAULT_BUFFER_SIZE):
        """
        :param udp_port:
        :type udp_port: int or None
        :param str tcp_address:
        :param int bufsize:
        """
        #: The buffer size (usually 4kB)
        self.bufsize = bufsize

        #: The UDP socket
        self.udp_sock = udp_socket(bind_port=udp_port)
        #: The address associated with the UDP socket
        self.udp_address = None

        # The TCP (client) socket
        self.tcp_sock = tcp_socket(connect_address=tcp_address)

        #: How to handle messages in the proxy protocol
        self.tcp_protocol = TCPDatagramProtocol()

    def udp_to_tcp(self):
        """ Forward received UDP datagrams over TCP.
        """
        # Receive the datagram, recording the originating address of the packet
        # (to allow directing of return packets)
        datagram, udp_address = self.udp_sock.recvfrom(self.bufsize)
        if udp_address != self.udp_address:
            logging.info("new UDP connection from {}".format(udp_address))
            self.udp_address = udp_address

        # Forward the datagram over TCP (prepending with the datagram length)
        self.tcp_sock.send(self.tcp_protocol.send(datagram))

    def tcp_to_udp(self):
        """ Unpack received TCP data and forward any datagrams over UDP.
        """
        data = self.tcp_sock.recv(self.bufsize)
        assert len(data) > 0, "Remote socket closed prematurely."
        for datagram in self.tcp_protocol.recv(data):
            # Forward the datagram to the last UDP address received from
            if self.udp_address is None:
                logging.warning("got TCP data before UDP 'connection' made")
                continue
            self.udp_sock.sendto(datagram, self.udp_address)

    def get_select_handlers(self):
        return {
            self.udp_sock: self.udp_to_tcp,
            self.tcp_sock: self.tcp_to_udp,
        }

    def close(self):
        self.udp_sock.close()
        self.tcp_sock.close()


class TCPtoUDP(DatagramProxy):
    """ Unpack datagrams sent over a TCP connection into UDP datagrams.

    This proxy sets up a TCP server and 'connects' to a specified UDP
    address. Datagrams sent to the TCP server are forwarded as UDP datagrams
    to the specified destination. UDP datagrams received are forwarded down
    the TCP connection.

    Since TCP is stream-based not datagram-based, each datagram is prefixed
    with a 32-bit number indicating the datagram's length in bytes.

    When a connection is made to the TCP server, all previous TCP connections
    are closed.
    """

    def __init__(self, tcp_port, udp_address,
                 bufsize=DEFAULT_BUFFER_SIZE):
        """
        :param tcp_port:
        :type tcp_port: int or None
        :param str udp_address:
        :param int bufsize:
        """
        #: The buffer size (usually 4kB)
        self.bufsize = bufsize

        #: The TCP server
        self.tcp_listen_sock = tcp_socket(bind_port=tcp_port)
        self.tcp_listen_sock.listen(1)

        #: The most recently connected socket to the server (or ``None`` if not
        #: connected)
        self.tcp_sock = None

        #: How to handle messages in the proxy protocol
        self.tcp_protocol = None
        #: The UDP socket
        self.udp_sock = udp_socket(connect_address=udp_address)

    def on_connect(self):
        """ Callback to handle new TCP connections.
        """
        if self.tcp_sock is not None:
            self.tcp_sock.close()

        self.tcp_sock, address = self.tcp_listen_sock.accept()
        self.tcp_protocol = TCPDatagramProtocol()
        logging.info("new TCP connection from {}".format(address))

    def udp_to_tcp(self):
        """ Forward received UDP datagrams over TCP.
        """
        datagram = self.udp_sock.recv(self.bufsize)
        if self.tcp_sock is None:
            logging.warning("got UDP data before TCP connection made")
            return
        self.tcp_sock.send(self.tcp_protocol.send(datagram))

    def tcp_to_udp(self):
        """ Unpack received TCP data and forward any datagrams over UDP.
        """
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
