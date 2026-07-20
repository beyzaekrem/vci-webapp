from ..exceptions import TriggerBoxError
from ..trigger_box_connection import trigger_box
from .base import ControllerComponent


class ModeControllModule(ControllerComponent):
    def switch_mode(self, mode: str) -> None:
        """Switches the server mode.

        The capture servers manage physical hardware and persist in specific operational modes
        (e.g. "record" for disk capture, "calibration" for calibration tasks). Each mode has different capabilities,
        some functions (aka. wrapped API endpoints) are only available in certain modes or give a different response
        to the same call.
        Switching the mode, takes active ownership of the hardware and server tasks. If another user/connection already
        has ownership ControlTakenError is raised. In this case, only API calls that do not interrupt the running
        session are allowed.

        Once you've successfully switched to a mode, you need to at least start the mode and the cameras with `start()`.

        **Modes**
        - **single**: capture single (disjointed) frames, process and download them immediately. Can take background images.
        - **record**: record raw images (disjointed or video) to server-disks.
        - **replay**: process and download images from server-disks.
        - **ring_buffer**: contionusly process and keep images in temporary ring-buffer memory.
            All frames in ring-buffer are download-able.
        - **calibration**: tasks for camera calibration. e.g.: detecting color and charuco boards.
        - virtual mode **observer**: does *not* change the server mode. Releases our hardware ownership (if we had it).

        - **server mode:** any
        - **API endpoint:** SWITCH_MODE, RELEASE_CONTROL

        Args:
            mode (str): the mode to switch to.

        Raises:
            ControlTakenError: another user already has server control, switching the mode was denied.
        """
        if mode == "observer":
            self.send("RELEASE_CONTROL")
        else:
            self.send("SWITCH_MODE", {"mode": mode})
        self.ui.debug(f"Mode switched to {mode}")

    def release_control(self, *, force: bool = False) -> None:
        """Release active control of the servers, if you had it.
        If another connection has control, ControlerTakenError is raised.
        If force=True is passed you forcefully release *their* control.

        - **server mode:** any
        - **API endpoint:** RELEASE_CONTROL

        Args:
            force (bool, optional): force other users to relase their control. Defaults to False.
        """
        self.send("RELEASE_CONTROL", {"force": force})

    def take_control(self, *, force: bool = False) -> None:
        """Take active control of the servers.
        If another connection has control, ControlTakenError is raised.
        If force=True is passed, you forcefully release their control and assume it yourself.

        - **server mode:** any
        - **API endpoint:** TAKE_CONTROL

        Args:
            force (bool, optional): force other users to release their control. Defaults to False.
        """
        self.send("TAKE_CONTROL", {"force": force})

    def start(self) -> None:
        """Starts the cameras and mode dependant server tasks.

        - **server mode:** any
        - **API endpoint:** START

        Raises:
            ControlTakenError: another user has taken server control. Action denied
        """
        self.send("START")
        self.ui.debug("Cameras started")

    def stop(self) -> None:
        """Stops the cameras and mode dependant server tasks.
        Attempts to stop hardware trigger signals.

        - **server mode:** any
        - **API endpoint:** STOP

        Raises:
            ControlTakenError: another user has taken server control. Action denied
        """
        self.send("STOP")
        self.ui.debug("Cameras stopped")
        try:
            trigger_box("off")
        except TriggerBoxError as e:
            self.ui.warning(f"Could not reach trigger box. {e}")

    def hard_reset(self) -> None:
        """Restarts the server script. For recoverability, this API endpoint can allways be called,
        regardless of active tasks.

        - **server mode:** any
        - **API endpoint:** HARD_RESET
        """
        self.send("HARD_RESET", wait=False)
        self.ui.info("Reset sent")

    def set_ignore_cameras(self, color_only: bool, camera_list: list[str] | None = None) -> None:
        """Set which cameras should be ignored on server startup. Hard reset the server for changes to take effect

        - **server mode:** any
        - **API endpoint:** SET_IGNORE_CAMERAS

        Args:
            color_only (bool): if True opens only color cameras. False - opens all cameras
            camera_list (list[str] | None, optional): list of camera_ids to be ignored. Defaults to None.
        """
        if camera_list is None:
            camera_list = []
        self.send(
            "SET_IGNORE_CAMERAS",
            {
                "color_only": color_only,
                "camera_list": camera_list,
            },
        )
        self.ui.info(f"Set color_only: {color_only}")
        if not camera_list:
            self.ui.info("Removed all cameras from ignore list.")
        else:
            self.ui.info(f"Added {camera_list} to ignore list")
        self.ui.info("Servers require hardreset for changes to take effect")

    def get_interface(self) -> dict:
        return self.request_dict("INTERFACE")
