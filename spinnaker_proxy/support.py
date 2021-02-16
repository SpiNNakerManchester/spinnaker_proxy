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

""" Simple support classes.
"""

import struct
from abc import abstractmethod, ABCMeta as Abstract


class TCPDatagramProtocol(object):
    """ A simple TCP-based protocol for transmitting/receiving datagrams.

    The protocol simply sends datagrams down the TCP connection proceeded by
    a 32-bit (network-order) unsigned integer which gives the length of the
    datagram (in bytes) that follows.
    """

    LENGTH = struct.Struct("!I")

    def __init__(self):
        # Buffer to hold incomplete datagrams received over TCP
        self.buf = b""

    def recv(self, tcp_data):
        """ Generate packets in incoming TCP data.

        :param bytes tcp_data:
            Raw data read from a TCP socket.
        :return:
            A series of datagrams (possibly none) received from the connection.
        :rtype: bytes
        """
        # Accumulate received data
        self.buf += tcp_data

        while len(self.buf) >= 4:
            datagram_length = self.LENGTH.unpack(self.buf[:4])[0]
            if len(self.buf) < 4 + datagram_length:
                break
            # A complete datagram has arrived, yield it
            datagram, self.buf = (
                self.buf[4:4 + datagram_length],
                self.buf[4 + datagram_length:]
            )
            yield datagram

    def send(self, datagram):
        """ Encode a datagram for transmission down a TCP socket.

        :param bytes datagram:
            The datagram to encode.
        :return:
            A series of bytes to send down the TCP socket.
        :rtype: bytes
        """
        return self.LENGTH.pack(len(datagram)) + datagram


class DatagramProxy(object, metaclass=Abstract):
    """ A simple proxy server which transparently forwards datagram-based\
        communications."""

    @abstractmethod
    def get_select_handlers(self):
        """ List the sockets to select on and their on-readable handlers.

        :return:
            All sockets should be selected for readability, and, when
            readable, that callback should be called.
        :rtype: dict(~socket.socket, callable)
        """
        raise NotImplementedError

    @abstractmethod
    def close(self):
        """ Close all open connections.
        """
        raise NotImplementedError
