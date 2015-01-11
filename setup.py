# Copyright ClusterHQ Limited. See LICENSE file for details.

"""
Setup Powerstrip.
"""
import os
from setuptools import setup, find_packages


with open("README.rst") as readme:
    description = readme.read()

setup(
    # This is the human-targetted name of the software being packaged.
    name="Powerstrip",
    # This is a string giving the version of the software being packaged.  For
    # simplicity it should be something boring like X.Y.Z.
    version="0.1",
    # This identifies the creators of this software.  This is left symbolic for
    # ease of maintenance.
    author="ClusterHQ Labs",
    # This is contact information for the authors.
    author_email="labs@clusterhq.com",
    # Here is a website where more information about the software is available.
    url="https://clusterhq.com/",

    # A short identifier for the license under which the project is released.
    license="Apache License, Version 2.0",

    # Some details about what Flocker is.  Synchronized with the README.rst to
    # keep it up to date more easily.
    long_description=description,

    install_requires=[
        "Twisted == 14.0.0",
        "PyYAML == 3.10",
        ],
    # Some "trove classifiers" which are relevant.
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        ],
    )
