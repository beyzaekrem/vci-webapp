import argparse
import threading
import traceback
from enum import Enum, auto
from pathlib import Path

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared import CAMERA_MANAGER, PERSISTENT_DATA, PERSISTENT_PATHS
from sparrow.modes.base_handler import BaseHandler
from sparrow.utils import logger


class ServerStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    FAILED = auto()


class SparrowServer:
    def __init__(self, port: int = 2443) -> None:
        self.port = port
        self.status = ServerStatus.PENDING
        self._finished_starting = threading.Event()  # event flags for testability
        self.server_instance = None

    def start(self) -> None:
        """Initializes and runs the server. Blocks until stopped."""
        try:
            # prepare server
            self.server_instance = gibbs.interceptor.Server(self.port)

            # open cameras, read settings, etc...
            my_handler = BaseHandler(self.server_instance)
            self.server_instance.set_handler(my_handler)

            # start server
            logger.info(f"Starting Server on port {self.port}")
            self._finished_starting.set()
            self.status = ServerStatus.RUNNING
            self.server_instance.run()  # opens server on port.
        except Exception as e:
            # this expection caused the server to crash
            logger.error(f"Server Error: {e}\n{traceback.format_exc()}")
            self._finished_starting.set()
            self.status = ServerStatus.FAILED

    def wait_until_ready(self, timeout: float = 30.0) -> None:
        """Blocks until the server signals it finished initializing (failed or succeeded)"""
        if not self._finished_starting.wait(timeout):
            msg = f"Server failed to start on port {self.port}"
            raise TimeoutError(msg)
        if self.status == ServerStatus.FAILED:
            msg = "Server failed to initialize."
            raise RuntimeError(msg)

    def stop(self) -> None:
        if self.server_instance:
            self.server_instance.stop()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Starts vci-capture server. Connects to cameras and handles image capture and data storage."
    )
    parser.add_argument(
        "--sim",
        nargs="?",
        const="sim_config/simulate_cameras.json",
        help="enables simulated cameras. Pass the path to  simulate_camera.json file to speficy. Default config is: sim_config/simulate_cameras.json",
    )
    return parser.parse_args()


def initialize_simulated_cameras(sim_config_path: str) -> None:
    if sim_config_path is None:
        return

    # set the path to load which cameras to simulate
    sim_config_path: Path = Path(sim_config_path)
    if not sim_config_path.is_file():
        sim_config_path = sim_config_path / "simulate_cameras.json"
    # set path to configs (calibration+rotations)
    CAMERA_MANAGER.configure_simulation(str(sim_config_path))
    PERSISTENT_PATHS.set_path(sim_config_path.parent)

    # capture an image and save and background for the sim cameras.
    CAMERA_MANAGER.setup_cameras()
    CAMERA_MANAGER.start_cameras()
    backgrounds = CAMERA_MANAGER.capture_images()
    CAMERA_MANAGER.stop_cameras()
    PERSISTENT_DATA.save_background_images(backgrounds)


if __name__ == "__main__":
    args = arguments()
    if args.sim:
        initialize_simulated_cameras(args.sim)

    s = SparrowServer()
    s.start()
