import os
import pathlib

import charonload
import torch  # noqa: F401

BUILD_TYPE = os.getenv("GIBBS_BUILD_TYPE") or "RelWithDebInfo"
charonload.module_config["gibbs"] = charonload.Config(
    project_directory=pathlib.Path(__file__).parent / "../gibbs",
    build_directory=pathlib.Path(__file__).parent / "../../build/gibbs",
    stubs_directory=pathlib.Path(__file__).parent / "../../typings",
    verbose=True,
    build_type=BUILD_TYPE,
)

from gibbs import *  # noqa: E402, F403
