import time
from threading import Thread

import sparrow.gibbs_wrapper as gibbs
from sparrow.gibbs_wrapper import interceptor
from sparrow.mode_shared import CAMERA_MANAGER, PERSISTENT_PATHS
from sparrow.modes.mode import ModeHandler
from sparrow.modes.mode_util import get_info, require_parameter
from sparrow.net.camera_system_data import CameraSystemDataSingleton
from sparrow.net.livestream_settings import LiveStreamSettings, ZoomParameters
from sparrow.net.streamable_camera import StreamableCameraManager
from sparrow.utils import logger


class LivestreamHandler(ModeHandler):
    pipeline = None

    @classmethod
    def mode_name(cls) -> str:
        return "livestream"

    @classmethod
    def mode_protected(cls) -> str:
        return False  # live stream mode does not keep control after initialization

    def __init__(self) -> None:
        super().__init__()
        logger.info("Initialize LivestreamHandler")
        CAMERA_MANAGER.setup_cameras()  # only runs if cameras are not set up already.
        CAMERA_MANAGER.stop_cameras()
        self.create_livestream()

    def create_livestream(self) -> None:
        logger.info("Starting Livestream")
        self.livestream_settings = LiveStreamSettings(PERSISTENT_PATHS.live_stream_settings_path)

        logger.info(f"Setting up livestram for cameras: {CAMERA_MANAGER.camera_ids}")

        # loads a separate settings file for livestreams. Checks the section "cameras" <camera_id> "saved_paramters"
        # can specify exposure ...
        for camera in CAMERA_MANAGER.cameras:
            settings = self.livestream_settings.get_camera_settings(camera.camera_id)
            # if there are saved parmaeters for this camera attempt to apply them...
            for saved_param in settings.get_saved_parameters():
                try:
                    StreamableCameraManager().get_camera_by_id(camera.camera_id).set_parameter(
                        saved_param.name, saved_param.value
                    )
                except Exception as e:
                    logger.error(f"Error setting parameter {saved_param.name} for camera {camera.camera_id}: {e}")
            # then start camera and start auto software trigger just in case.
            camera.start()
            camera.set_software_fps(50)
            camera.start_software_auto_trigger()

        # reload parameters to ensure that even trigger source is updated
        CameraSystemDataSingleton().performReload(lambda x: x.update_parameter_values())

        self.pipeline = gibbs.tasks.LivestreamPipeline(CAMERA_MANAGER.cameras, [])

        # Start the pipeline threads
        self.pipeline.Run()
        logger.info("Live stream pipeline is running!")

    def on_stop(self) -> None:
        """Stop the livestream handler."""
        logger.info("Stopping LivestreamHandler")
        if self.pipeline:
            self.pipeline.Stop()

        CAMERA_MANAGER.stop_cameras()

    # WEBSOCKET STUFF # TODO
    @interceptor.path_handler("GET_ALL_INFO")
    def _path_get_all_info(self, message: interceptor.MessageIn) -> None:
        """Get all information that the UI client needs."""
        websocket_structure = CameraSystemDataSingleton().getCurrentCameraSystemData()
        payload = interceptor.Payload.FromDict(websocket_structure.as_dict())
        message.Acknowledge([payload])

    @interceptor.path_handler("SET_PARAMETER")
    def _path_set_parameter(self, message: interceptor.MessageIn) -> None:
        """Set a parameter to a value for a camera. Also save it in the livestream settings on disk to use again."""
        info = get_info(message)
        camera_id: int = require_parameter(info, "camera_id")
        param_name = require_parameter(info, "name")
        parma_value = require_parameter(info, "value")
        camera = StreamableCameraManager().get_camera_by_id(camera_id)
        camera.stop()
        try:
            camera.set_parameter(param_name, parma_value)

            # save in livestream settings so it will be restored when handler is restarted
            settings = self.livestream_settings.get_camera_settings(camera.camera_id)
            settings.set_saved_parameter(param_name, parma_value)
            self.livestream_settings.save()
        except Exception as e:
            logger.error(f"Error setting parameter: {e}")

        time.sleep(0.1)
        camera.start()

        CameraSystemDataSingleton().performReload(lambda x: x.update_parameter_values())
        message.Acknowledge()

    @interceptor.path_handler("SET_PARAMETER_INCREMENTAL")
    def _path_set_parameter_incremental(self, message: interceptor.MessageIn) -> None:
        """Set a parameter incrementally for a specific camera."""
        info = get_info(message)
        camera_id: int = require_parameter(info, "camera_id")
        param_name: str = require_parameter(info, "name")
        parma_value: int = require_parameter(info, "value")

        camera = StreamableCameraManager().get_camera_by_id(camera_id)
        current_value = camera.get_parameter(param_name)
        camera.set_parameter(param_name, current_value + parma_value)

        def reload_and_ack() -> None:
            CameraSystemDataSingleton().performReload(lambda x: x.update_parameter_values())
            message.Acknowledge()

        Thread(target=reload_and_ack).start()

    @interceptor.path_handler("POLL_LIVESTREAM_IMAGE")
    def _path_poll_livestream_image(self, message: gibbs.interceptor.MessageIn) -> None:
        """Poll for the latest image from a livestream."""

        info = get_info(message)
        camera_id: int = require_parameter(info, "camera_id")
        stream_id: str = require_parameter(info, "stream_id")

        stream = self.pipeline.GetLivestream(stream_id)
        # If the stream does not exist, we create it
        if stream is None:
            img_w, img_h = 5328 / 2, 4608 / 2
            zoom_params = self.livestream_settings.get_zoom_parameters(stream_id)
            if zoom_params is not None:
                center_x = zoom_params.center_x
                center_y = zoom_params.center_y
                client_size = tuple(zoom_params.client_size)
                zoom_full = zoom_params.zoom_factor
            else:
                client_size = (1024, 1024)
                center_x = img_w / 2
                center_y = img_h / 2
                zoom_full = min(client_size[0] / img_w, client_size[1] / img_h)
            self.pipeline.AddLivestream(
                gibbs.tasks.Livestream(
                    stream_id,
                    camera_id,
                    gibbs.tasks.ZoomParams(
                        center_x=center_x, center_y=center_y, client_size=client_size, zoom_factor=zoom_full
                    ),
                    buffer_size=50,
                )
            )
            logger.info(f"Added Livestream: {stream_id}")
            stream = self.pipeline.GetLivestream(stream_id)
        capture_time = time.time()  # todo measure this in the capture thread

        def send_img() -> None:
            jpg_tensor = None

            wait_until_next_try = 0.05
            print_every_s = 3
            tries = 0
            while (jpg_tensor is None or jpg_tensor.numel() == 0) and self.pipeline.is_running:
                jpg_tensor = stream.GetImage()
                tries += 1
                if jpg_tensor is None or jpg_tensor.numel() == 0:
                    if tries % (int(print_every_s / wait_until_next_try)) == 0:
                        logger.info(f"Livestream {stream.ID()} did not return an image yet. Retrying...")
                    time.sleep(wait_until_next_try)

            if jpg_tensor is None:
                message.ErrorResponse("The Livestream was closed while waiting for image")
            else:
                jpg_bytes = jpg_tensor.numpy().tobytes()

                message.Acknowledge(
                    [
                        gibbs.interceptor.Payload.FromDict({"stream_id": stream.ID(), "capture_time": capture_time}),
                        gibbs.interceptor.Payload.WrapPyBytes(jpg_bytes),
                    ]
                )

        # Run the image sending in a separate thread to avoid blocking
        Thread(target=send_img).start()

    @interceptor.path_handler("GET_IMAGE_FULL")
    def _path_get_image_full(self, message: interceptor.MessageIn) -> None:
        """Get the full resolution image from a camera."""

        info = get_info(message)
        camera_id: str = require_parameter(info, "camera_id")

        stream_id = "download_full_image_" + str(camera_id)
        # todo do not hardcode this
        img_w, img_h = 5328 / 2, 4608 / 2
        zoom_params = self.livestream_settings.get_zoom_parameters(stream_id)
        if zoom_params is not None:
            center_x = zoom_params.center_x
            center_y = zoom_params.center_y
            client_size = tuple(zoom_params.client_size)
            zoom_factor = zoom_params.zoom_factor
        else:
            center_x = img_w / 2
            center_y = img_h / 2
            client_size = (int(img_w), int(img_h))
            zoom_factor = 1.0
        self.pipeline.AddLivestream(
            gibbs.tasks.Livestream(
                stream_id,
                camera_id,
                gibbs.tasks.ZoomParams(
                    center_x=center_x, center_y=center_y, client_size=client_size, zoom_factor=zoom_factor
                ),
                buffer_size=50,
            )
        )
        stream = self.pipeline.GetLivestream(stream_id)

        no_image_yet = True
        while no_image_yet:
            jpg_tensor = stream.GetImage()

            # Skip if no data yet
            if jpg_tensor is None or jpg_tensor.numel() == 0:
                logger.debug(f"Livestream {stream.ID()} did not return an image yet.")
                time.sleep(0.1)
            else:
                no_image_yet = False
                jpg_bytes = jpg_tensor.numpy().tobytes()
                logger.debug(f"{stream.ID()} image bytes length: {len(jpg_bytes)}")

                message.Acknowledge(
                    [
                        gibbs.interceptor.Payload.FromDict({"camera_id": camera_id}),
                        gibbs.interceptor.Payload.WrapPyBytes(jpg_bytes),
                    ]
                )

    @interceptor.path_handler("SET_STREAM_PARAMETERS")
    def _path_set_stream_parameters(self, message: gibbs.interceptor.MessageIn) -> None:
        """Set parameters for a livestream."""
        info = get_info(message)

        stream_id = require_parameter(info, "stream_id")
        parameters = require_parameter(info, "parameters")

        stream = self.pipeline.GetLivestream(stream_id)
        if stream is None:
            logger.debug(f"Stream with ID {stream_id} not found.")
            message.Acknowledge()
            return

        current_params = stream.Params

        # todo request this from ximea api
        image_width = 5328 / 2  # known image width
        image_height = 4608 / 2  # known image height

        if "client_width" in parameters:
            current_params.client_size = (int(parameters["client_width"]), current_params.client_size[1])
        if "client_height" in parameters:
            current_params.client_size = (current_params.client_size[0], int(parameters["client_height"]))
        if "zoom_center_x" in parameters:
            current_params.center_x = parameters["zoom_center_x"]
        if "zoom_center_y" in parameters:
            current_params.center_y = parameters["zoom_center_y"]
        if "reset_zoom_center" in parameters:
            current_params.center_x = image_width / 2
            current_params.center_y = image_height / 2
        if "zoom_factor" in parameters:
            current_params.zoom_factor = parameters["zoom_factor"]
        if "zoom_factor_relative" in parameters:
            if parameters["zoom_factor_relative"] > 0:
                current_params.zoom_factor *= 2
            else:
                current_params.zoom_factor /= 2
        if "zoom_center_x_relative" in parameters and parameters["zoom_center_x_relative"] != 0:
            current_params.center_x = round(
                current_params.center_x + parameters["zoom_center_x_relative"] / current_params.zoom_factor * 200
            )
        if "zoom_center_y_relative" in parameters and parameters["zoom_center_y_relative"] != 0:
            current_params.center_y = round(
                current_params.center_y + parameters["zoom_center_y_relative"] / current_params.zoom_factor * 200
            )
        if "fix_full_size" in parameters:
            current_params.center_x = image_width / 2
            current_params.center_y = image_height / 2
            zoom_factor_full = min(
                current_params.client_size[0] / image_width, current_params.client_size[1] / image_height
            )
            current_params.zoom_factor = zoom_factor_full

        # Save zoom parameters to settings
        zp = ZoomParameters(
            center_x=current_params.center_x,
            center_y=current_params.center_y,
            client_size=current_params.client_size,
            zoom_factor=current_params.zoom_factor,
        )
        self.livestream_settings.set_zoom_parameters(stream_id, zp)

        message.Acknowledge()
