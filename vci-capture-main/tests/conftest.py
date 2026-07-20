# this folder contains fixtures avaibale to all subfodlers.
from collections.abc import Generator
from pathlib import Path

import pytest

# from sparrow.gibbs_wrapper import interceptor
from sparrow.mode_shared import CAMERA_MANAGER, PERSISTENT_DATA, PERSISTENT_PATHS, PERSISTENT_RECORD
from sparrow.mode_shared.camera_manager import CameraManager
from sparrow.mode_shared.persistent import PersistentData
from sparrow.mode_shared.persistent_paths import PersistentPaths

# interceptor.setup_logger(interceptor.debug, interceptor.debug)


# -- paths --
@pytest.fixture(scope="session")
def data_path() -> Path:
    return Path("tests/data")


@pytest.fixture(scope="session")
def tmp_path() -> Path:
    p = Path("data/tmp")
    p.mkdir(exist_ok=True, parents=True)
    return p


@pytest.fixture(scope="session")
def outdata_path() -> Path:
    p = Path("data")
    p.mkdir(exist_ok=True)
    return p


@pytest.fixture(scope="session")
def config_folder(data_path: Path) -> Path:
    return data_path / "config"


@pytest.fixture(scope="session")
def image_folder(data_path: Path) -> Path:
    return data_path / "image"


@pytest.fixture(scope="session")
def background_folder(data_path: Path) -> Path:
    return data_path / "background"


@pytest.fixture(scope="session")
def sim_camera_config(data_path: Path) -> Path:
    return data_path / "simulated_cameras.json"


@pytest.fixture
def with_persistent_path(tmp_path: Path) -> Generator[PersistentPaths]:
    with PERSISTENT_PATHS.temporary_values():
        PERSISTENT_PATHS.set_path(tmp_path)
        yield PERSISTENT_PATHS


# re-define this fixture in lower level conftest or test__.py module to set a different path.
@pytest.fixture(scope="module")
def record_save_path(tmp_path: Path) -> Path:
    return tmp_path / "media"


@pytest.fixture(scope="module", autouse=True)
def with_record_save_paths(record_save_path: Path) -> Generator[PersistentPaths]:
    """points the persitent record save paths to a tmp path"""
    record_paths = PERSISTENT_RECORD.paths
    with record_paths.temporary_values():
        record_paths.media_root = record_save_path
        record_paths.ssd_range = range(3)  # would be overkill to create so many sub_folders
        # make sure the paths exist so we can save into them.
        print("set record save path to ", record_paths)
        for path in record_paths.ssds:
            path.mkdir(exist_ok=True, parents=True)
        yield PERSISTENT_RECORD


## -- simualted cameras, CAMERA_MANAGER, PERSISTENT and initilized BaseHandler --
# setup of simulated cameras:
# 1. simualte_cameras, 2.simualted_calibration, 3. base_handler.
# then, call fully_uncalibrated or fully_calibrated to set/unset calibration.


@pytest.fixture(scope="session")
def simulate_cameras(sim_camera_config: Path) -> CameraManager:
    """configures CAMERA_MANAGER to open simulated cameras instead of physicall cameras.
    Must be called before CAMERA_MANAGER.setup_cameras() is called. Aka, before BaseHandler is created."""
    CAMERA_MANAGER.configure_simulation(str(sim_camera_config))
    return CAMERA_MANAGER


@pytest.fixture(scope="session")
def simualted_calibration(data_path: Path, config_folder: Path) -> None:
    PERSISTENT_PATHS.set_path(data_path)
    PERSISTENT_PATHS.calibration_file_path = config_folder / "simulated_calib.json"
    PERSISTENT_PATHS.rotation_file_path = config_folder / "simulated_rotations.json"
    # also grabs background images, rotations and live stream settings from data_path


@pytest.fixture
def fully_uncalibrated(camera_manager: CameraManager) -> Generator[PersistentData]:
    """load uncalibrated data into global shared PERSISTENT_PATHS"""
    with PERSISTENT_PATHS.temporary_values():
        PERSISTENT_PATHS.set_path("/dev/null/fake")
        PERSISTENT_DATA.load(camera_ids=camera_manager.camera_ids)
        yield PERSISTENT_DATA
    # reset paths and re-load persistent data
    PERSISTENT_DATA.load(camera_ids=camera_manager.camera_ids)


@pytest.fixture
def fully_calibrated(camera_manager: CameraManager, data_path: Path, config_folder: Path) -> PersistentData:
    """load calibrated data into global shared PERSISTENT_PATHS"""
    PERSISTENT_PATHS.set_path(data_path)
    PERSISTENT_PATHS.calibration_file_path = config_folder / "simulated_calib.json"
    PERSISTENT_PATHS.rotation_file_path = config_folder / "simulated_rotations.json"
    PERSISTENT_DATA.load(camera_ids=camera_manager.camera_ids)
    return PERSISTENT_DATA
