import sys

required_version = (3, 8)

if sys.version_info[:2] < required_version:  # pragma: no cover
    msg = "%s requires Python %d.%d+" % (__package__, *required_version)
    raise RuntimeError(msg)

del required_version
del sys


import pathlib

import charonload
import torch

PROJECT_ROOT_DIRECTORY = pathlib.Path(__file__).parents[2]

charonload.module_config["_c_interceptor"] = charonload.Config(
    project_directory=PROJECT_ROOT_DIRECTORY / "src/interceptor/_C",
    build_directory=PROJECT_ROOT_DIRECTORY / "build",
    stubs_directory=PROJECT_ROOT_DIRECTORY / "typings",
    verbose=False,
)

from _c_interceptor import *
