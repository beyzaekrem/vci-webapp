import pytest
from client import Client, Response

from sparrow.image_processing.processing_steps import StepDefaults

# fixtures

@pytest.fixture
def with_software_triggering(client: Client) -> None:
    r: Response = client.send("SET_TRIGGER_SOURCE", {"source": "Software"})

## tests

def test_connection(client: Client) -> None:
    assert client.client.is_connected(), "client should be connected"


def test_get_some_info(client: Client) -> None:
    r: Response = client.send("GET_CAMERA_INFO")
    r.get_dict()


def test_get_status(client: Client) -> None:
    r: Response = client.send("STATUS")
    r.get_dict()


def test_get_rec_info(client: Client) -> None:
    r: Response = client.send("RECORDING_INFO")
    r.get_dict()


def test_get_calib_file(client: Client) -> None:
    r: Response = client.send("GET_CALIBRATION_FILE", {"steps": StepDefaults.PROCESSED})
    r.get_dict()


def test_get_raw_calib_file(client: Client) -> None:
    r: Response = client.send("GET_RAW_CALIBRATION")
    r.get_dict()


def test_get_camera_rotations(client: Client) -> None:
    r: Response = client.send("GET_CAMERA_ROTATIONS")
    r.get_dict()


def test_start(client: Client) -> None:
    client.send("START")
    client.send("STOP")


def test_control(client: Client) -> None:
    client.send("TAKE_CONTROL")
    client.send("RELEASE_CONTROL")


def test_force_control(client: Client) -> None:
    p = {"force": True}
    client.send("TAKE_CONTROL", p)
    client.send("RELEASE_CONTROL", p)


def test_set_trigger_source_software(client: Client) -> None:
    r: Response = client.send("SET_TRIGGER_SOURCE", {"source": "Software"})


def test_set_trigger_source_hardware(client: Client) -> None:
    r: Response = client.send("SET_TRIGGER_SOURCE", {"source": "Hardware"})


def test_set_software_auto_trigger(client: Client, with_software_triggering) -> None:
    client.send("SET_SOFTWARE_AUTO_TRIGGER", {"enabled": True, "fps": 15})
    client.send("SET_SOFTWARE_AUTO_TRIGGER", {"enabled": False})


def test_software_trigger_single(client: Client, with_software_triggering) -> None:
    r: Response = client.send("SOFTWARE_TRIGGER_SINGLE")
