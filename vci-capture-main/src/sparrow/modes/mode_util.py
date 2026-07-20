from __future__ import annotations

import io

import psutil
from PIL import Image

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import interceptor
from sparrow.utils import logger


def get_info(message: interceptor.MessageIn, *, required: bool = False) -> dict:
    info = {}
    if len(message.payload) > 0:
        info = interceptor.Payload.ToDict(message.payload[0])
    elif required:
        msg = f"Message {message.path} requries a payload"
        raise interceptor.WrongPayloadError(msg)
    return info


def require_parameter(
    info: dict, parameter: str, valid_types: type | tuple[type | None] | None = None
) -> str | int | float | list | None:
    """Wrapps dictionary access, throwing WrongPayloadError if the paramter(key) doesnt exist.
    Optionally verifies the type of the parameter-value agains given valid_types.

    e.g.: `require_parameter(info, "fps", (int, None))` - "fps" must exist and either return be int or None.

    Args:
        info (dict): payload paramters passed via Message.
        parameter (str): target parameter(dict key) to retrieve.
        valid_types (type | tuple[type  |  None] | None, optional): Indicate types the parameter value may have. Defaults to no type checking.
    Raises:
        interceptor.WrongPayloadError: paramter is missing, or of an invalid type.

    Returns:
        str | int | float | list | None: the value of the parameter
    """
    if parameter not in info:
        msg = f"Missing required parameter {parameter}"
        raise interceptor.WrongPayloadError(msg)
    val = info.get(parameter)

    # Check type only if expected_type is provided
    if valid_types is not None:
        types_tuple = valid_types if isinstance(valid_types, tuple) else (valid_types,)

        # Separate None/NoneType from actual classes for isinstance checks
        allowed_classes = tuple(t for t in types_tuple if t is not None and t != type(None))
        allows_none = None in types_tuple or type(None) in types_tuple

        if val is None:
            if not allows_none:
                msg = f"Parameter '{parameter}' cannot be None"
                raise interceptor.WrongPayloadError(msg)
        elif not isinstance(val, allowed_classes):
            # Format expected types nicely for the error message
            expected_names = ", ".join([t.__name__ for t in allowed_classes])
            if allows_none:
                expected_names += " or None"

            msg = f"Parameter '{parameter}' should be of type {expected_names} but is {type(val).__name__}"
            raise interceptor.WrongPayloadError(msg)
    return val


def check_ram() -> None:
    # Get the current memory usage
    memory_info = psutil.virtual_memory()

    # RAM usage details
    logger.info(f"Total RAM: {memory_info.total / (1024 ** 3):.2f} GB")
    logger.info(f"Available RAM: {memory_info.available / (1024 ** 3):.2f} GB")
    logger.info(f"Used RAM: {memory_info.used / (1024 ** 3):.2f} GB")
    logger.info(f"RAM Usage Percentage: {memory_info.percent}%")


def check_storage() -> None:
    disk_info = psutil.disk_usage("/")
    # storage details
    logger.info(f"Total Storage: {disk_info.total / (1024 ** 3):.2f} GB")
    logger.info(f"Used Storage: {disk_info.used / (1024 ** 3):.2f} GB")
    logger.info(f"Free Storage: {disk_info.free / (1024 ** 3):.2f} GB")
    logger.info(f"Storage Usage Percentage: {disk_info.percent}%")


def filter_images(images: list[gibbs.GibbsImage], requested_camera_ids: list[str] | None) -> list:
    if requested_camera_ids is None:
        return images
    return [i for i in images if i.camera_id in requested_camera_ids]


def clean_requested_camera_ids(requested_camera_ids: list[str] | None, valid_camera_ids: list[str]) -> list:
    """Removes any camera_ids that are not valid.
    Re-orders the camera_ids to follow the sorting of the valid_camera_ids list.

    If requested_camera_ids is None, returns all valid_camera_ids.

    Args:
        requested_camera_ids (list[str]): list of camera_ids requested.
        valid_camera_ids (list[str]): list of valid camera_ids. E.g. activly connected and running or available in stored recording.

    Returns:
        list: camera_ids thate are both requested and valid.
    """
    if requested_camera_ids is None:
        requested_camera_ids = valid_camera_ids
    else:
        requested_camera_ids = [cam_id for cam_id in valid_camera_ids if cam_id in requested_camera_ids]
    return requested_camera_ids


def save_torch_payload(payload, cam_id: str) -> None:  # noqa: ANN001
    memory_view = payload.PyMemoryView()
    logger.info(f"memory view nbytes {cam_id, memory_view.nbytes}")

    image_bytes = io.BytesIO(memory_view)
    image = Image.open(image_bytes)
    image.save(f"__{cam_id}.jpg")
    logger.info(f"image saved __{cam_id}_.jpg")
