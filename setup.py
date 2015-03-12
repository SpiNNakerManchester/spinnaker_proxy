from setuptools import setup, find_packages
import sys

setup(
    name="spinnaker_proxy",
    version="0.0.1-dev",
    packages=[],
    scripts=["spinnaker_proxy/spinnaker_proxy.py"],

    # Metadata for PyPi
    author="Jonathan Heathcote",
    description="A proxy-server for SpiNNaker systems.",
    license="GPLv2",

    # Requirements
    install_requires=["six"],
)
