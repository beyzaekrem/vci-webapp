import pytest

import sparrow.gibbs_wrapper as gibbs
from sparrow.modes import mode_util


def test_require_parameter_basic() -> None:
    mode_util.require_parameter({"fps": 10}, "fps")


def test_require_parameter_type_indicated() -> None:
    mode_util.require_parameter({"fps": 10}, "fps", int)


def test_require_parameter_passed_none() -> None:
    # should genreally be fine
    mode_util.require_parameter({"fps": None}, "fps")


def test_require_parameter_type_wrong() -> None:
    with pytest.raises(gibbs.interceptor.WrongPayloadError):
        mode_util.require_parameter({"fps": "10"}, "fps", int)


def test_require_parameter_typed_none_err() -> None:
    with pytest.raises(gibbs.interceptor.WrongPayloadError):
        mode_util.require_parameter({"fps": None}, "fps", int)


def test_require_parameter_type_or_none_passed_type() -> None:
    mode_util.require_parameter({"fps": 10}, "fps", (int, None))


def test_require_parameter_type_or_none_passed_none() -> None:
    mode_util.require_parameter({"fps": None}, "fps", (int, None))


def test_require_parameter_type_or_none_passed_err() -> None:
    with pytest.raises(gibbs.interceptor.WrongPayloadError):
        mode_util.require_parameter({"fps": "10"}, "fps", (int, None))
