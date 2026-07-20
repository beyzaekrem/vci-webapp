import logging
from pathlib import Path

from sparrow.mode_shared import CAMERA_MANAGER, PERSISTENT_PATHS
from sparrow.server import SparrowServer


def run_simulated_environment() -> None:
    logging.basicConfig(level=logging.INFO)

    # 1. Mimic 'simualte_cameras' fixture
    sim_config = Path("tests/data/sim_camera_config.json")
    CAMERA_MANAGER.configure_simulation(str(sim_config))

    # 2. Mimic 'simualted_calibration' fixture
    data_path = Path("tests/data")
    PERSISTENT_PATHS.set_path(data_path)
    PERSISTENT_PATHS.calibration_file_path = data_path / "config" / "simulated_calib.json"
    PERSISTENT_PATHS.rotation_file_path = data_path / "config" / "simulated_rotations.json"

    # 3. Start the server (blocking)
    print("Starting simulated server on port 2445... Press Ctrl+C to stop.")
    srv = SparrowServer(port=2445)
    srv.start()


if __name__ == "__main__":
    run_simulated_environment()
