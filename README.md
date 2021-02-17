[![Build Status](https://github.com/SpiNNakerManchester/spinnaker_proxy/workflows/Build/badge.svg?branch=master)](https://github.com/SpiNNakerManchester/spinnaker_proxy/actions?query=workflow%3A%22Build%22+branch%3Amaster)
[![Coverage Status](https://coveralls.io/repos/github/SpiNNakerManchester/spinnaker_proxy/badge.svg?branch=master)](https://coveralls.io/github/SpiNNakerManchester/spinnaker_proxy?branch=master)

SpiNNaker Proxy
===============

A small proxy utility which allows reliable basic operation of SpiNNaker boards
over the open Internet.

In particular, the proxy enables reliably booting SpiNNaker boards over the open
Internet, a task usually made impossible by the need to communicate via port
54321 (which is filtered out by many ISPs). On top of this, the boot protocol
relies on reliable delivery of UDP packets which is simply unrealistic on the
open Internet.

Typical usage is as follows:

                 LAN              .  Internet  .       User's Machine
                                  .            .
    +-----------+     +--------+  .            .  +--------+     +-----------+
    | SpiNNaker |<===>| Proxy  |<================>| Proxy  |<===>| SpiNNaker |
    | Board     |     | Server |  .            .  | Client |     | Software  |
    +-----------+     +--------+  .            .  +--------+     +-----------+
                                  .            .
Where SpiNNaker software is a tool like
[ybug](https://github.com/SpiNNakerManchester/spinnaker_tools) or
[sPyNNaker](https://github.com/SpiNNakerManchester/sPyNNaker8).

By transmitting boot packets using a different port number between the proxy
client and server, the packets are not stripped out by most ISPs. Further, the
proxy can use TCP to send boot packets between the client and server to ensure
no packets are dropped while crossing the Internet.

[Further documentation](http://spinnakermanchester.github.io/spinnaker_proxy/)
(internal API docs) is available.

Installation
------------

The proxy can be installed from
[PyPi](https://pypi.python.org/pypi/spinnaker_proxy) as follows:

    pip install spinnaker_proxy

Alternatively, you can install the script manually using setuptools from a
checked out copy of this repository:

    python setup.py install

Quick-Start
-----------

On a machine on the same LAN as the SpiNNaker machine you wish to use, run the
following to start an instance of the proxy server:

    spinnaker_proxy.py -s SPINN_HOSTNAME

Where `SPINN_HOSTNAME` is the hostname of the SpiNNaker board. On the machine
you are running SpiNNaker software:

    spinnaker_proxy.py -c PROXY_SERVER_HOSTNAME

Where `PROXY_SERVER_HOSTNAME` is the hostname of the machine you started the
proxy server on.  You can now point your SpiNNaker software at `localhost` and
everything should work normally.

### Reliable Booting: TCP Tunnelling

The proxy can optionally tunnel boot commands via a TCP connection. To do this
simply add the `-t` flag to both the proxy server and client:

    # Proxy Server
    spinnaker_proxy.py -s -t SPINN_HOSTNAME

    # Proxy Client
    spinnaker_proxy.py -c -t PROXY_HOSTNAME


Default Ports
-------------

By default the following ports are used between the proxy server and client.

| Port  | Description  |
| ----- | ------------ |
| 17894 | SCP packets  |
| 17895 | Boot packets |

These can be changed using command line options which can be listed using
`spinnaker_proxy.py --help`.


Warnings
========

The proxy will only forward SCP and boot commands. To send/receive SDP packets
to/from a machine you should communicate directly with the machine, bypassing
the proxy.

The proxy server will behave oddly if multiple proxy clients attempt to connect.

The proxy client will behave oddly if multiple applications attempt to connect.
