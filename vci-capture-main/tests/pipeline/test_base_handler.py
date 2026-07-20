# ruff: noqa: S101  # noqa: INP001


import pytest

from sparrow.modes.base_handler import MODES, BaseHandler

###  Test cases for functionality of the basehandler / common across all handlers

### run with : python -m pytest tests/pipeline


@pytest.fixture(params=[m for m in MODES if m != "livestream"])
def any_mode_name(request: str) -> str:
    return request.param


@pytest.fixture(params=[True, False])
def any_verbosity(request: str) -> bool:
    return request.param


# -- test ---


def test_status_mode_init(base_handler: BaseHandler, any_mode_name: str) -> None:
    base_handler.switch_mode(any_mode_name)


def test_status_call_basic(base_handler: BaseHandler, any_mode_name: str, any_verbosity: bool) -> None:
    try:
        base_handler.switch_mode(any_mode_name)
    except Exception as e:
        print(f"failed to switch to mode {any_mode_name}", e)
    status = base_handler.get_status(verbose=any_verbosity)
    assert status["mode"] == any_mode_name  # we should always have switched into the requested mode.
    assert status["camera_ids"] != None
