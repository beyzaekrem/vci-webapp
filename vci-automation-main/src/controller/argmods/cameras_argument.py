import argparse
import fnmatch

from ..controller import SystemLayoutReader


def resolve_cameras(
    nargs: list[str],
    system_layout: SystemLayoutReader,
    connected_cameras: list[str] | None = None,
) -> list[str] | None:
    """
    Converts a set of camera ID arguments (nargs) into a final list of selected
    camera IDs by resolving wildcards (e.g., 'M*').

    Args:
        nargs: A set of camera ID or wildcard strings provided by the user (e.g., {'C000', 'M*', 'Z999'}).
        connected_cameras: A list of all available camera IDs currently connected (e.g., ['C000', 'M0001', 'M0002', 'Z999']).

    Returns:
        A list of selected and resolved camera IDs, or None if the input list is empty
        and 'ALL' was not specified.
    """

    if connected_cameras is None:
        connected_cameras = system_layout.expected_cameras()

    preset_keys = {"CENTER": system_layout.get_center_cameras(), "ALL": connected_cameras}

    if nargs == ["ALL"]:
        return None  # all cameras.

    selected_cameras: list = []
    unmatched_patterns = []

    # TODO: let servers resolve the wildcard. Our expected_cameras list can be outdated.

    for key in set(nargs):
        matched = []
        if key in preset_keys:  # is a preset
            resolve = preset_keys[key]
            connected = [cam_id for cam_id in resolve if cam_id in connected_cameras]
            matched.extend(connected)
        elif "*" in key:  # is a pattern
            for cam_id in connected_cameras:
                if fnmatch.fnmatch(cam_id, key):
                    matched.append(cam_id)
        elif key in connected_cameras:
            matched.append(key)

        if len(matched) == 0:
            unmatched_patterns.append(key)
        else:
            selected_cameras.extend(matched)

    # remove camera ids
    for key in set(nargs):
        if key.startswith("no-"):
            cam_id = key[3:]
            if cam_id in selected_cameras:
                selected_cameras.remove(cam_id)
                unmatched_patterns.remove(key)

    if len(unmatched_patterns) > 0:
        print(
            Warning(
                f"The following camera ID(s) or pattern(s) did not match any cameras: "
                f"{', '.join(sorted(unmatched_patterns))}"
            )
        )

    return sorted(set(selected_cameras))


def add_cameras_argument(
    parser: argparse.ArgumentParser,
    default: str | list[str] = "ALL",
    description: str = "capture",
    name: str = "--cams",
    short_name: str | None = None,
    *,
    required: bool = False,
) -> argparse.ArgumentParser:
    """
    Adds the --cams argument to select cameras. User can specify a list of camera IDs.
    They can also use wildcards like 'M*' to indicate all cameras of Type M.

    Args:
        parser: The ArgumentParser object to add the argument to.
        default: The default camera selection. Can be "ALL" or a list of IDs/patterns.
        required: Whether the argument is strictly required. Note: If the default is not ["ALL"],
                  and required is False, passing no argument will use the empty list.
    """

    # Convert the list of default strings/patterns into a single space-separated string
    # for argparse default display, though Python receives it as a list if provided.

    arg_names: list[str] = [name]
    if short_name is not None:
        arg_names.append(short_name)

    help_msg = (
        f"{description} "
        "Specify via ID (e.g. C0001), wildcard pattern (e.g 'M*' - all Mono cameras) or preset group  (e.g. CENTER). "
        "Wildcard patterns must be enclosed in quotes. "
        "Available preset groups: ALL - all cameras, CENTER - the color cameras around the central ring. "
        f"You can mix the different styles: e.g. {name} C0001 M* CENTER. A camera is selected when it's included in at least one specifier. "
    )
    if default:
        if not isinstance(default, list):
            default = [default]
        default_str = " ".join(default)
        help_msg += f"Default here: {default_str}."

    parser.add_argument(
        *arg_names,
        nargs="*",  # Allows 0 or more arguments, which is needed to support the default
        default=default,
        help=help_msg,
        required=required,
    )
    # Note: When nargs='*', if the argument is omitted, the `default` list is used.
    # If the argument is provided with no values (e.g., `--cams`), an empty list [] is used.

    return parser
