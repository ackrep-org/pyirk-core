#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import setuptools
from setuptools import setup, find_packages


packagename = "pyerk"  # this has to be renamed

# consider the path of `setup.py` as root directory:
PROJECTROOT = os.path.dirname(sys.argv[0]) or "."
release_path = os.path.join(PROJECTROOT, "src", packagename, "release.py")
with open(release_path, encoding="utf8") as release_file:
    __version__ = release_file.read().split('__version__ = "', 1)[1].split('"', 1)[0]


with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read()

setup(
    name=packagename,
    version=__version__,
    author="Carsten Knoll",
    author_email="firstname.lastname@posteo.de",
    packages=find_packages("src"),
    package_dir={"": "src"},
    # url="https://codeberg.org/username/reponame",
    license="GPLv3",
    description="(Python based) Easy Representation of Knowledge (pyERK)",
    long_description="""
(Python based) Easy Representation of Knowledge (pyERK).

- Inspired by OWL, but more expressive
- Inspired by Wikidata, but much simpler
- Inspired by SUO-KIF, but with less brackets
- Represented directly in python
- Designed to formally represent knowledge (including meta levels)
""",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
    ],
    entry_points={"console_scripts": [f"{packagename}={packagename}.script:main"]},
)
