import copy
from typing import ClassVar


class ProcessingSteps:
    """
    - PROCESSED: Full pipeline ["debayer_malvar", "superkernel"]
    - SMOL: Full pipeline with half resolution ["debayer_subsample", "superkernel"]
    - TINY: Full pipeline with downscaled images ["debayer_subsample", "superkernel", "small_scale_4"]
    - LINEAR: Processed linear image ["debayer_malvar", "white_balance", "color_correction", "undistort"]. e.g for exr format

    - DEBAYERED: mostly unprocessed image, only debayer ["debayer_malvar"]
    - TINY_UNCALIBRATED: downscaled image that requires no calibration ["debayer_subsample","non_linear","hist_scale","small_scale_4"]
    - RAW: raw image []
    - PRETTY_RAW: raw but values adjusted ["white_balance", "non_linear", "hist_scale"]

    - COLOR_CHECKER: preset for color checker detection during calibration ["debayer_subsample"]
    - CHARUCO: preset for charuco board detection during calibration ["debayer_malvar", "non_linear", "hist_scale"]

    (superkernel components: "white_balance", "color_correction", "undistort", "non_linear", "hist_scale")
    """

    # full pipeline in different resolutions
    PROCESSED: ClassVar[dict] = {
        "C*": [{"debayer": {"method": "malvar"}}, {"superkernel": {}}],
        "D*": [{"undistort": {}}],
        "M*": [
            {"superkernel": {}},
            {"hist_scale": {}},
        ],
    }
    PROCESSED_DEPTH: ClassVar[dict] = {
        "C*": [{"debayer": {"method": "malvar"}}, {"superkernel": {}}],
        "D*": [
            {"undistort": {}},
            {"depth_scale": {"capture_max": 16384, "output_range": [0, 4500]}},
        ],
        "M*": [{"superkernel": {}}, {"hist_scale": {}}],
    }
    SMOL: ClassVar[dict] = {
        "C*": [{"debayer": {"method": "subsample"}}, {"superkernel": {}}],
        "D*": [{"undistort": {}}],
        "M*": [{"superkernel": {}}, {"hist_scale": {}}],
    }

    TINY: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "malvar"}},
            {"superkernel": {}},
            {"size_scale": {"factor": 0.25}},
        ],
        "D*": [{"undistort": {}}],
        "M*": [{"superkernel": {}}, {"hist_scale": {}}, {"size_scale": {"factor": 0.25}}],
    }
    LINEAR: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "malvar"}},
            {"white_balance": {}},
            {"color_correction": {}},
            {"undistort": {}},
        ],
        "D*": [{"undistort": {}}],
        "M*": [{"hist_scale": {}}, {"undistort": {}}],
    }

    # partial pipeline
    DEBAYERED: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "malvar"}},
        ],
        "D*": [],
        "M*": [],
    }
    TINY_UNCALIBRATED: ClassVar[dict] = {
        "C*": [
            {"debayer": {"method": "subsample"}},
            {"non_linear": {}},
            {"size_scale": {"factor": 0.25}},
        ],
        "D*": [{"size_scale": {"factor": 0.25}}],
        "M*": [
            {"non_linear": {}},
            {"hist_scale": {}},
            {"size_scale": {"factor": 0.25}},
        ],
    }
    RAW: ClassVar[dict] = {"C*": [], "M*": [], "D*": []}
    PRETTY_RAW: ClassVar[dict] = {  # output image is still bayered but values aka colors adjusted as much as possible
        "C*": [
            {"white_balance": {}},
            {"non_linear": {}},
        ],
        "D*": [],
        "M*": [
            {"non_linear": {}},
            {"hist_scale": {}},
        ],
    }

    # presets for calibration steps
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

    @staticmethod
    def OVERWRITE_NO_ROTATION(steps: dict[str, list]) -> dict[str, list]:
        """
        Disables automatic rotation (rot90) that compensates for hardware setup.
        Does *not* change the steps in-place.
        """
        # you can always add rotate:False to disallow the automatic rotation correction
        steps = copy.deepcopy(steps)
        for _, step_list in steps.items():
            step_list: list = step_list
            for step in step_list:
                if "rotate" in step:
                    step["rotate"] = {"enabled": False}  # change exisitng rotate instruction with enabled False
            step_list.append(
                {"rotate": {"enabled": False}}
            )  # add an explicit no-rotation instruction (disable auto rotate)
        return steps

    @staticmethod
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


# Automatically generate the map:
PROCESSING_STEPS_MAP = {}
for attr_name in dir(ProcessingSteps):
    # Check for uppercase attributes that are not internal
    if attr_name.isupper() and not attr_name.startswith("_"):
        attr_value = getattr(ProcessingSteps, attr_name)
        # Check if the attribute is a list (your step pipeline)
        if isinstance(attr_value, dict):
            # *** Store the key in lowercase ***
            PROCESSING_STEPS_MAP[attr_name.lower()] = attr_value
