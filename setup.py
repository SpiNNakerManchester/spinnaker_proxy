# Copyright (c) 2015-2016 The University of Manchester
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

from setuptools import setup

setup(
    name="spinnaker_proxy",
    version="2.0.4",
    packages=[],
    scripts=["spinnaker_proxy/spinnaker_proxy.py"],

    # Metadata for PyPi
    author="Jonathan Heathcote",
    description="A proxy-server for SpiNNaker systems.",
    license="GPLv2",
    url="https://github.com/SpiNNakerManchester/spinnaker_proxy",
)
