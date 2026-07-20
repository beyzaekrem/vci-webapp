

from .base import ControllerComponent


class ParametersModule(ControllerComponent):
    def set_depth_active(self, image_type: str = "depth") -> None:
        """
        Select image capture mode for depth cameras (orbbec).
        Can either capture **depth** images, **color** images or **mono** images.

        - **server mode:** any
        - **API endpoint:** SET_DEPTH_MODE

        Args:
            image_type (str, optional): choice [depth, color, mono]. Defaults to depth
        """
        try:
            self.send("SET_DEPTH_MODE", {"depth_mode": image_type})
        except RuntimeError as e:
            self.ui.error("  ", e, " \n")

    def set_software_trigger(self, state: bool = True) -> None:  # noqa: FBT001, FBT002
        """Set the trigger source to software (True) or hardware (False).

        - **server mode:** any
        - **API endpoint:** SET_PARAMETERS

        Args:
            state (bool, optional): If true enables software trigger, otherwise enables hardware trigger.
            Defaults to True.
        """

        trigger_source = 3 if state else 1  # 3: Software, 1: Hardware
        self.send("SET_PARAMETERS", {"int:trigger_source": trigger_source})

    def set_threshold(self, value: float = 0.5) -> None:
        """
        Sets the binarization threshold for masks in the ring_buffer. (foreground/background segmenation)

        Converts soft masks (range [0, 1]) into binary foreground/background masks.
        Pixels with values >= threshold are set to foreground (1).

        A higher threshold results in a stricter foreground definition,
        effectively pruning semi-transparent or low-confidence edge regions.

        - **server mode:** ring_buffer
        - **API endpoint:** SET_THRESHOLD

        Args:
            value (float): threshold value in range of [0,1]. Defaults to: 0.5.
        """
        self.send("SET_THRESHOLD", {"threshold": value})

    def set_exposure_and_gain(self, exposure: int, gain: int, camera_type: str = "color") -> None:
        """Set exposure and gain for a given camera_type.

        - **server mode:** any
        - **API endpoint:** SET_PARAMETERS

        Args:
            exposure (int): exposure time in milliseconds.
            gain (int): gain
            camera_type (str, optional): filters which cameras to apply the expsure and gain to
                        choice: [color, mono, depth]. Defaults to "color".
        """
        if exposure < 100:  # noqa: PLR2004
            self.ui.warning(f"Did you swap exposure and gain? Exposure: {exposure}, Gain: {gain}")

        if gain > 24:  # noqa: PLR2004
            self.ui.warning("Highest gain supported by XIMEA cameras is 24")

        self.send("SET_PARAMETERS", {"camera_type": camera_type, "int:gain": gain, "int:exposure": exposure})

    def set_fps(self, fps: int) -> None:
        """Sets (software) fps for ring_buffer or record mode.

        - **server mode:** ring_buffer, record
        - **API endpoint:** SET_FPS

        Args:
            fps (int): _description_
        """
        self.send("SET_FPS", {"fps": fps})

    def set_parameter(self, parameter: str, value: any, parameter_type: str = "int") -> None:
        """Set a specific parameter (e.g., gain, exposure) with the provided value and type.

        - **server mode:** any
        - **API endpoint:** SET_PARAMETERS

        Args:
            parameter (str): name of parameter (e.g gain, exposure)
            value (any): string, float or int value to set the parameter to.
            parameter_type (str, optional): choice [int, float, string]. Defaults to "int".
        """
        self.send("SET_PARAMETERS", {f"{parameter_type}:{parameter}": value})

    def set_recording_name(self, recording_name: str, fps: int | None = None, *, invalid_ok: bool = False) -> None:
        """Set the recording name for record or replay mode.

        In record mode, this name serves as the unique identifier for saving raw images to disk.
        This allows the specific image set to be selected for subsequent download, deletion or overwriting.

        - **server mode:** record, replay
        - **API endpoint:** SET_RECORDING_NAME

        Args:
            recording_name (str): the name used to create a new recording or select an existing one.
            fps (int|None): when creating a recording, the replay fps can be set. (This does not determine the actual trigger fps.)
            invalid_ok (bool, optional): if True does not throw an error when setting the recording name fails.
            Defaults to False.
        """
        try:
            self.send("SET_RECORDING_NAME", {"recording_name": recording_name, "fps": fps})
        except RuntimeError as e:
            if invalid_ok:
                self.ui.warning(e)
            else:
                raise
