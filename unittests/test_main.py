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

import pytest
import spinnaker_proxy.spinnaker_proxy as main
import spinnaker_proxy.support as support
# pylint: disable=protected-access, attribute-defined-outside-init
# pylint: disable=redefined-outer-name, unused-argument


def test_argument_parsing():
    args = main._parse_arguments(["-s", "a"])
    assert len(sorted(x for x in dir(args) if not x.startswith("_"))) == 10
    assert args.server
    assert not args.client
    assert args.target == "a"

    args = main._parse_arguments(["-c", "a"])
    assert not args.server
    assert args.client
    assert args.target == "a"
    # Check defaults
    assert args.boot_port == 54321
    assert args.scp_port == 17893
    assert args.scp_tunnel_port == 17894
    assert args.boot_tunnel_port == 17895
    assert not args.sdp_via_tcp
    assert not args.boot_via_tcp
    assert not args.quiet

    args = main._parse_arguments([
        "-q",
        "--scp-port", "10",
        "--scp-tunnel-port", "11",
        "--boot-port", "12",
        "--boot-tunnel-port", "13",
        "--sdp-via-tcp",
        "--boot-via-tcp",
        "-c", "abc"])
    assert args.target == "abc"
    assert args.boot_port == 12
    assert args.scp_port == 10
    assert args.scp_tunnel_port == 11
    assert args.boot_tunnel_port == 13
    assert args.sdp_via_tcp is True
    assert args.boot_via_tcp is True
    assert args.quiet is True


def test_argument_errors(capsys):
    # Verify that we need one of -c or -s
    with pytest.raises(SystemExit):
        main._parse_arguments(["a"])
    captured = capsys.readouterr()
    assert "one of the arguments" in captured.err
    with pytest.raises(SystemExit):
        main._parse_arguments(["-c", "-s", "a"])
    captured = capsys.readouterr()
    assert "not allowed with" in captured.err
    # Verify that target is required
    with pytest.raises(SystemExit):
        main._parse_arguments(["-c"])
    captured = capsys.readouterr()
    assert "the following arguments are required: target" in captured.err
    # Verify that -h prints a usage message and exits
    with pytest.raises(SystemExit):
        main._parse_arguments(["-h"])
    captured = capsys.readouterr()
    assert "usage:" in captured.out


@pytest.fixture
def do_not_connect():
    """
    Disables doing the TCP connection step; we don't want to have to care about
    configuring dummy servers to receive connections here.
    """
    value = support._SKIP_TCP_CONNECT
    support._SKIP_TCP_CONNECT = True
    yield None
    support._SKIP_TCP_CONNECT = value


class MockArgs():
    """ A mock of the arguments out of arg parsing
    """
    def __init__(self, client, sdp, boot):
        self.client = client
        self.server = not client
        self.target = "localhost"
        self.sdp_via_tcp = sdp
        self.boot_via_tcp = boot
        self.scp_port = 13530
        self.boot_port = 13531
        self.scp_tunnel_port = 13532
        self.boot_tunnel_port = 13533


@pytest.mark.parametrize("client", [True, False])
@pytest.mark.parametrize("sdp", [True, False])
@pytest.mark.parametrize("boot", [True, False])
def test_proxy_construction(client, sdp, boot, do_not_connect):
    proxies = list(main._construct_proxies(MockArgs(client, sdp, boot)))
    assert len(proxies) == 2
    for p in proxies:
        assert isinstance(p, support.DatagramProxy)
        p.close()
