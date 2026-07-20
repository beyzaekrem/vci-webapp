# noqa: INP001
import threading
from collections.abc import Generator

import pytest
from client import Client
from helpers import ensure_calibration

from sparrow.mode_shared.camera_manager import CAMERA_MANAGER, CameraManager
from sparrow.mode_shared.persistent import PERSISTENT_DATA, PersistentData
from sparrow.server import SparrowServer


# test flags.
def pytest_addoption(parser) -> None:
    parser.addoption("--hardware", action="store_true", default=False, help="Run integration tests on real hardware")


# -- Server & Client --


@pytest.fixture(scope="session")
def port() -> int:
    return 2470


@pytest.fixture(scope="session")
def camera_manager(request) -> CameraManager:
    if request.config.getoption("--hardware"):
        # Return the actual production CameraManager/Singleton
        ret: CameraManager = CAMERA_MANAGER
    else:
        # Return the simulated one from your other fixture
        ret: CameraManager = request.getfixturevalue("simulate_cameras")
    return ret


@pytest.fixture(scope="session")
def persistent_data() -> PersistentData:
    return PERSISTENT_DATA


@pytest.fixture(scope="session")
def sparrow_server(request, port, camera_manager, persistent_data) -> Generator[SparrowServer, None, None, None]:
    """Starts the API server. Uses simulated cameras unless --hardware is passed."""

    use_hardware = request.config.getoption("--hardware")

    if not use_hardware:
        # Manually trigger simulation setup if not using hardware
        # This ensures 'simulate_cameras' and 'simulated_calibration' run
        request.getfixturevalue("simulate_cameras")
        request.getfixturevalue("simualted_calibration")
        print("Starting SparrowServer with SIMULATED hardware\n")
    else:
        print("Starting SparrowServer with REAL hardware\n")

    server = SparrowServer(port=port)
    threading.Thread(target=server.start, daemon=True).start()
    server.wait_until_ready(30)
    camera_manager.force_software_trigger = True
    ensure_calibration(persistent_data.calibration_data, camera_manager)

    yield server
    server.stop()


@pytest.fixture(scope="module")
def client(port: int, sparrow_server: SparrowServer) -> Client:
    """Minimal test client connected to API server. Simuated cameras."""
    return Client(port)
