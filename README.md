SpiNNaker Proxy
---------------

This small utility implements a simple UDP proxy server for SpiNNaker systems to
allow booting of SpiNNaker boards over the open internet.

Though SDP functions correctly over the internet, the SpiNNaker boot protocol
uses port 54321 which is filtered out by many ISPs. As a result it impossible to
remotely boot a SpiNNaker board over many real-world internet connections. This
proxy server is designed to be run within the same LAN as a SpiNNaker board and
transparently forward packets between remote users and the SpiNNaker system.

Installation
------------

    python setup.py install

or

    pip install spinnaker_proxy


Usage
-----

Set up a proxy for a SpiNNaker board (but not a BMP):

    spinnaker_proxy.py SPINN_HOSTNAME

Where `SPINN_HOSTNAME` is the hostname of the board to proxy.

Alternatively, a BMP can also be proxied:

    spinnaker_proxy.py SPINN_HOSTNAME BMP_HOSTNAME

Where `SPINN_HOSTNAME` is the hostname of the board to proxy and `BMP_HOSTNAME`
is the hostname of the BMP to proxy.


Default Ports
-------------

By default the following ports are opened by the proxy:

Port  | Destination            | Description
----- | ---------------------- | ------------------------
17894 | `SPINN_HOSTNAME`:17893 | SpiNNaker SCP port
17895 | `BMP_HOSTNAME`:17893   | BMP SCP port
17896 | `SPINN_HOSTNAME`:54321 | SpiNNaker boot port

See `--help` for details on how to change these mappings.


Warning
-------

This proxy will behave oddly if there are multiple simultaneous users. Since
SpiNNaker boards also tend to do the same in these circumstances, this is not
considered a problem.
