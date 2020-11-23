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
from abc import abstractmethod, ABCMeta
import six


class TCPDatagramProtocol(object):
    """ A simple TCP-based protocol for transmitting/receiving datagrams.

    The protocol simply sends datagrams down the TCP connection proceeded by\
    a 32-bit (network-order) unsigned integer which gives the length of the\
    datagram (in bytes) that follows.
    """

    LENGTH = struct.Struct("!I")

    def __init__(self):
        # Buffer to hold incomplete datagrams received over TCP
        self.buf = b""

    def recv(self, tcp_data):
        """ Generate packets in incoming TCP data.

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

        Parameters
        ----------
        datagram : bytes
            The datagram to encode.

        Returns
        ----------
        bytes
            A series of bytes to send down the TCP socket.
        """
        return self.LENGTH.pack(len(datagram)) + datagram


@six.add_metaclass(ABCMeta)
class DatagramProxy(object):
    """ A simple proxy server which transparently forwards datagram-based\
        communications."""

    @abstractmethod
    def get_select_handlers(self):
        """ List the sockets to select on and their on-readable handlers.

        Returns
        -------
        {socket: func, ...}
            All sockets should be selected for readabillity, and, when\
            readable, func should be called.
        """
        raise NotImplementedError()

    @abstractmethod
    def close(self):
        """ Close all open connections.
        """
        raise NotImplementedError()
