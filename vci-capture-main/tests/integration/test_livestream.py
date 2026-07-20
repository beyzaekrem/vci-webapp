# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100

import helpers
import pytest
from client import Client, Response


## fixtures
@pytest.fixture(scope="module", autouse=True)
def switch_to_record(client: Client) -> None:
    client.switch_mode("livestream")
    yield
    print("stop livestream")
    client.send("STOP")
    helpers.set_auto_trigger(client, enabled=True, fps=None)


def test_get_all_info(client: Client) -> None:
    r: Response = client.send("GET_ALL_INFO")


def test_set_parameter(client: Client) -> None:
    r: Response = client.send("SET_PARAMETER", {"camera_id": 0, "name": "exposure", "value": 4000})
    # TODO test parmater that is read only
    # TODO test unknown paramter


def test_set_parameter_incremental(client: Client) -> None:
    r: Response = client.send("SET_PARAMETER_INCREMENTAL", {"camera_id": 0, "name": "exposure", "value": 500})


def test_poll_livestream_image(client: Client) -> None:
    r: Response = client.send(
        "POLL_LIVESTREAM_IMAGE", {"camera_id": 0, "stream_id": "livestream_requested_by_test_client"}
    )


def test_get_image_full(client: Client) -> None:
    r: Response = client.send("GET_IMAGE_FULL", {"camera_id": 0})


def test_set_stream_parameters(client: Client) -> None:
    stream_id = "livestream_requested_by_test_client"
    r: Response = client.send("POLL_LIVESTREAM_IMAGE", {"camera_id": 0, "stream_id": stream_id})
    r: Response = client.send(
        "SET_STREAM_PARAMETERS",
        {"parameters": {"client_width": 512, "client_height": 512, "zoom_factor": 3}, "stream_id": stream_id},
    )
