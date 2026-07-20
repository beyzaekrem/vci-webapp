import fnmatch

from pydantic import BaseModel, field_validator

from .util import CLI_GROUP_IMAGE_CONFIGURATION, CliArg, ScriptArgumentField
from controller.controller import SystemLayoutReader


def _as_camera_list(value: str | list[str] | tuple[str, ...] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def resolve_cameras(
    nargs: list[str],
    system_layout: SystemLayoutReader,
    connected_cameras: list[str] | None = None,
) -> list[str] | None:
    """
    Convert camera ID arguments into a final list of selected camera IDs.
    Supports wildcards (e.g. ``M*``), ``CENTER``, ``ALL``, and ``no-<camera_id>`` exclusions.
    """
    if connected_cameras is None:
        connected_cameras = system_layout.expected_cameras()

    preset_keys = {"CENTER": system_layout.get_center_cameras(), "ALL": connected_cameras}

    if nargs == ["ALL"]:
        return None

    selected_cameras: list[str] = []
    unmatched_patterns: list[str] = []

    for key in set(nargs):
        matched = []
        if key in preset_keys:
            resolved = preset_keys[key]
            matched.extend(cam_id for cam_id in resolved if cam_id in connected_cameras)
        elif "*" in key:
            matched.extend(cam_id for cam_id in connected_cameras if fnmatch.fnmatch(cam_id, key))
        elif key in connected_cameras:
            matched.append(key)

        if not matched:
            unmatched_patterns.append(key)
        else:
            selected_cameras.extend(matched)

    for key in set(nargs):
        if key.startswith("no-"):
            cam_id = key[3:]
            if cam_id in selected_cameras:
                selected_cameras.remove(cam_id)
            if key in unmatched_patterns:
                unmatched_patterns.remove(key)

    if unmatched_patterns:
        print(
            Warning(
                "The following camera ID(s) or pattern(s) did not match any cameras: "
                f"{', '.join(sorted(unmatched_patterns))}"
            )
        )

    return sorted(set(selected_cameras))


def cameras_arg(
    default: str | list[str] | None = "ALL",
    description: str = "capture",
    name: str = "--cams",
    short_name: str | None = None,
    *,
    required: bool = False,
    group: str = CLI_GROUP_IMAGE_CONFIGURATION,
):
    default_values = _as_camera_list(default)
    option_strings = [name]
    if short_name is not None:
        option_strings.append(short_name)

    help_msg = (
        f"{description} "
        "Specify via ID (e.g. C0001), wildcard pattern (e.g 'M*' - all Mono cameras) or preset group (e.g. CENTER). "
        "Wildcard patterns must be enclosed in quotes. "
        "Available preset groups: ALL - all cameras, CENTER - the color cameras around the central ring. "
        f"You can mix the different styles: e.g. {name} C0001 M* CENTER. "
        "A camera is selected when it's included in at least one specifier."
    )

    class CamerasArgMixin(BaseModel):
        cams: list[str] | None = ScriptArgumentField(
            default=... if required else default_values,
            description=help_msg,
            json_schema_extra={
                "examples": [["ALL"], ["CENTER"], ["C0001", "M*"], ["ALL", "no-C0001"]],
            },
            cli=CliArg(option_strings=option_strings, group=group, metavar="CAMERA"),
        )

        @field_validator("cams", mode="before")
        @classmethod
        def validate_cams(cls, value: str | list[str] | tuple[str, ...] | None) -> list[str] | None:
            if value is None:
                if required:
                    raise ValueError("Camera selection is required.")
                return None
            return _as_camera_list(value)

        def resolve_cameras(
            self,
            system_layout: SystemLayoutReader,
            connected_cameras: list[str] | None = None,
        ) -> list[str] | None:
            if self.cams is None:
                return None
            return resolve_cameras(self.cams, system_layout, connected_cameras)

    return CamerasArgMixin
