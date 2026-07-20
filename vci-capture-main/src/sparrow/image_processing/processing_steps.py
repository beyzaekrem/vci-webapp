from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import ClassVar

from sparrow.modes.handler_exceptions import InvalidProcessingStepError


def get_command(step: dict[str:dict]) -> tuple[str, dict]:
    """
    Ensures the dict is a well formed command.
    Returns: the command name and the paramter dict.
    Raises: InvalidProcessingStepError
    """
    if len(step) != 1:
        raise InvalidProcessingStepError(step, "Processing step is empty or malformed")

    command, params = next(iter(step.items()))

    if not isinstance(params, dict):
        raise InvalidProcessingStepError(
            command, f"Step {step}. Invalid parameter value type: {type(params)}. Must be a dictionary."
        )
    return command, params


def steps_contain(steps: dict | list, step_key: str) -> bool:
    """checks if an entire steps dict[camera_id: step_list] contains step_key anywhere
    or, checks is a step_list of a specific camera contains the key.
    """
    if isinstance(steps, dict):  # we got an entire steps dict[camera_id: step_list]
        for step_list in steps.values():
            for step in step_list:
                if step_key in step:
                    return True
        return False
    return any(step_key in step for step in steps)  # steps is a list


def append_step(steps: dict | list, instert_step: dict | str) -> dict:
    if isinstance(instert_step, str):
        instert_step = {instert_step: True}
    if isinstance(steps, dict):
        for step_list in steps.values():
            step_list.append(instert_step)
    else:
        steps.append(instert_step)
    return steps


def de_wildcard(steps: dict[str : list[dict]], camera_ids: list[str]) -> dict:
    """
    Resolves wildcard keys (e.g. "C*") in a steps dictionary agains the given camera_ids list.
    """

    resolved_steps = {}
    for wildcard_key, step_list in steps.items():
        if "*" in wildcard_key:
            for cam_id in camera_ids:
                if fnmatch.fnmatch(cam_id, wildcard_key):
                    resolved_steps[cam_id] = step_list
    return resolved_steps


# region Default Steps
@dataclass
class StepDefaults:
    DEBAYERED: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
        ],
        "D*": [],
        "M*": [],
    }

    UNCALIBRATED: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
            {"non_linear": {}},
        ],
        "D*": [],
        "M*": [{"non_linear": {}}, {"hist_scale": {}}],
    }

    RAW: ClassVar[dict] = {"*": []}

    COLOR_PRETTY: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "malvar"}},
            {"white_balance": {}},
            {"color_correction": {}},
            {"non_linear": {}},
        ],
        "D*": [],
        "M*": [{"non_linear": {}}, {"hist_scale": {}}],
    }

    PROCESSED: ClassVar[dict] = {
        "C*": [{"debayer": {"method": "malvar"}}, {"superkernel": {}}, {"rotate": {"rot90": 1}}],
        "D*": [],
        "M*": [{"superkernel": {}}, {"hist_scale": {}}],
    }

    SMOL: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
            {"superkernel": {}},
        ],
        "D*": [],
        "M*": [{"superkernel": {}}, {"hist_scale": {}}],
    }

    RING_BUFFER: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
            {"superkernel": {}},
        ],
        "D*": [],
        "M*": [{"subsample": {"stride": 2}}, {"superkernel": {}}, {"hist_scale": {}}],
    }

    COLOR_CHECKER: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
        ],
        "D*": [],
        "M*": [{"non_linear": {}}, {"hist_scale": {}}],
    }
    CHARUCO: ClassVar[dict] = (
        {  # charuco disables rotation by default. Charuco calibration should be done on run-rotated images.
            "C*": [
                {"debayer": {"method": "malvar"}},
                {"non_linear": {}},
                {"rotate": {"enabled": False}},
            ],
            "D*": [{"rotate": {"enabled": False}}],
            "M*": [
                {"non_linear": {}},
                {"hist_scale": {}},
                {"rotate": {"enabled": False}},
            ],
        }
    )

    @classmethod
    def get_all(cls) -> dict[str, dict]:
        return {name: val for name, val in vars(cls).items() if name.isupper()}


# endregion
