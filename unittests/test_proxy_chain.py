# Copyright (c) 2017-2021 The University of Manchester
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

from functools import partial
import struct
import threading

from spinnaker_proxy.proxies import (
    TCPtoUDP, UDPtoTCP, UDPtoUDP, tcp_socket, udp_socket)
from spinnaker_proxy.spinnaker_proxy import run_proxies

# We're using 4 byte messages to test with
TCP_FORMAT = struct.Struct("!Ibbbb")
UDP_FORMAT = struct.Struct("bbbb")


class Runner:
    """
    Handles running the proxies in parallel with the test machinery and
    shutting that all down neatly.
    """
    __slots__ = ["_target", "_stopper", "_thread", "_exn"]

    def __init__(self, target):
        self._target = target
        self._stopper = threading.Event()
        self._thread = None
        self._exn = None

    def _run(self):
        try:
            self._target(self._stopper)
        except Exception as e:  # pylint: disable=broad-except
            self._exn = e

    def __enter__(self):
        self._thread = threading.Thread(target=self._run)
        self._thread.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stopper.set()
        self._thread.join(1)
        if not exc_type and self._exn:
            raise self._exn
        return False


def test_tcp_to_udp_proxy():
    proxy = TCPtoUDP(12369, ("localhost", 12370))
    with Runner(partial(run_proxies, [proxy])):
        with tcp_socket(connect_address=("localhost", 12369)) as s:
            with udp_socket(bind_port=12370) as r:
                s.send(TCP_FORMAT.pack(4, 0, 1, 2, 3))
                assert UDP_FORMAT.unpack(r.recv(32)) == (0, 1, 2, 3)


def test_udp_to_tcp_proxy():
    with tcp_socket(bind_port=12369) as tcp_listen_sock:
        tcp_listen_sock.listen(1)

        proxy = UDPtoTCP(12368, ("localhost", 12369))
        with Runner(partial(run_proxies, [proxy])):
            with udp_socket(connect_address=("localhost", 12368)) as s:
                s.send(UDP_FORMAT.pack(0, 2, 4, 6))
                r, a = tcp_listen_sock.accept()
                # Ensure that we're not getting sniped from another system
                assert a[0] == '127.0.0.1'
                try:
                    assert TCP_FORMAT.unpack(r.recv(32)) == (4, 0, 2, 4, 6)
                finally:
                    r.close()


def test_udp_to_udp_proxy():
    proxy = UDPtoUDP(12370, ("localhost", 12371))
    with Runner(partial(run_proxies, [proxy])):
        with udp_socket(connect_address=("localhost", 12370)) as s:
            with udp_socket(bind_port=12371) as r:
                s.send(UDP_FORMAT.pack(3, 5, 7, 9))
                assert UDP_FORMAT.unpack(r.recv(32)) == (3, 5, 7, 9)


def test_proxy_chain():
    # Threads a message through a chain of three proxies!
    p2 = TCPtoUDP(12369, ("localhost", 12370))
    p3 = UDPtoTCP(12368, ("localhost", 12369))
    p1 = UDPtoUDP(12370, ("localhost", 12371))
    with Runner(partial(run_proxies, [p1, p2, p3])):
        with udp_socket(connect_address=("localhost", 12368)) as s:
            with udp_socket(bind_port=12371) as r:
                s.send(UDP_FORMAT.pack(11, 13, 17, 19))
                assert UDP_FORMAT.unpack(r.recv(32)) == (11, 13, 17, 19)
                s.send(UDP_FORMAT.pack(23, 27, 29, 31))
                assert UDP_FORMAT.unpack(r.recv(32)) == (23, 27, 29, 31)
