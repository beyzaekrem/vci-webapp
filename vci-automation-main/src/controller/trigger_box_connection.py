import interceptor
import requests

from controller.components.connection import Connection

from .exceptions import TriggerBoxError
from .system_layout_reader import SystemLayoutReader


def trigger_box_new(state="on") -> str:
    """Set Hardware Trigger on/off

    Args:
        state (str): "on", "off", "single", "set_fps_X".

    Returns:
        response message (str)

    Raises:
        RequestError
    """
    lr = SystemLayoutReader()
    controller = Connection("controller", *lr.get_control_address())
    params = interceptor.Payload.FromDict({"commands": state})
    msg = interceptor.MessageOut("TRIGGER_BOX", [params])
    ret = controller.send_message(msg)
    res = ret.payload[0].ToDict()
    return res


def trigger_box(state="on") -> str:
    trigger_box_ip = "http://10.3.10.20:8080/"
    try:
        response = requests.get(f"{trigger_box_ip}{state}")
        if response.status_code == 200:  # and response.text in state: todo bäh
            return response.text
        raise TriggerBoxError(
            f"Failed to call f'{trigger_box_ip}{state}', status code: {response.status_code}. Response text: {response.text}"
        )
    except requests.exceptions.ConnectionError as e:
        raise TriggerBoxError("\nFailed to reach triggerbox:", e, "\n")
