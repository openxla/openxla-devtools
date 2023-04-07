# Copyright 2023 The OpenXLA Authors
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import json
from pathlib import Path
from setuptools import setup, find_namespace_packages

SETUP_PY_PATH = Path(__file__).resolve()
SOURCE_DIR = SETUP_PY_PATH.parent
VERSION_INFO_FILE = SOURCE_DIR / "version_info.json"

with open(SOURCE_DIR / "README.md", "rt") as f:
  README = f.read()


def load_version_info():
  with open(VERSION_INFO_FILE, "rt") as f:
    return json.load(f)


try:
  version_info = load_version_info()
except FileNotFoundError:
  print("version_info.json not found. Using defaults")
  version_info = {}

PACKAGE_SUFFIX = version_info.get("package-suffix") or ""
PACKAGE_VERSION = version_info.get("package-version") or "0.0dev1"

setup(
    name=f"openxla-dev-tools{PACKAGE_SUFFIX}",
    version=f"{PACKAGE_VERSION}",
    author="OpenXLA Authors",
    author_email="iree-discuss@googlegroups.com",
    description="OpenXLA Development Tools",
    long_description=README,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
    ],
    url="https://github.com/openxla/iree",
    python_requires=">=3.8",
    zip_safe=True,
    packages=find_namespace_packages(include=[
        "openxla.dev_tools",
        "openxla.dev_tools.*",
    ]),
    entry_points={
        "console_scripts": [
            "openxla-workspace = openxla.dev_tools.workspace.__main__:main"
        ],
    },
    install_requires=[],
)
