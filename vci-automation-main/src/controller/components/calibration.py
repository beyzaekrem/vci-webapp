import interceptor

from controller.components.connection_manager import Connection
from controller.logging_config import logger

from ..output_writers.image_writer import ImageEntry
from ..processing_steps import ProcessingSteps
from .base import ControllerComponent


class CalibrationModule(ControllerComponent):
    def set_raw_calibration(self, calibration_json: dict) -> None:
        self.send("SET_CALIBRATION_FILE", calibration_json)

    def set_camera_rotations(self, rotations: dict) -> None:
        self.send("SET_CAMERA_ROTATIONS", rotations)

    def set_charuco_board(self, dict_name: str, size: tuple[int], square_length: float, marker_length: float) -> None:
        parameters = {
            "dict_name": dict_name,
            "size": size,
            "square_length": square_length,
            "marker_length": marker_length,
        }
        self.send("SET_CHARUCO_BOARD", parameters=parameters)

    def handle_calibration(self, path: str, parameters: dict | None = None) -> list[tuple[dict, list[ImageEntry]]]:
        """Polls API endpoint (path+parameters) from all connected servers.
        The first element of a reponse is expected to be a dict. And all others are optional Images.

        Args:
            path (str): API endpoint
            parameters (dict | None, optional): optional parameters for API endpoint. Defaults to None.

        Returns:
            list[tuple[dict, list[ImageEntry]]]: a detection_info dict and image_entires per server.
        """

        def _response_callback(
            response: interceptor.MessageIn, connection: Connection
        ) -> list[tuple[dict, list[ImageEntry]]]:
            if not response.payload:
                logger.warning(
                    f"     Payload is empty. Path: {response.path}, Server: {connection.servername}, Cameras: {connection.camera_ids}"
                )
                return None
            detection_info = self.get_dict_from_responses(response)
            image_entries = self.image_writer.save_images_from_response(response, connection)
            return detection_info, image_entries

        return self.send(path, parameters=parameters, callback=_response_callback)

    def color_checker_detection(
        self,
        detection_processing_steps: dict = ProcessingSteps.COLOR_CHECKER,
        requested_camera_ids: list[str] | None = None,
        method: str = "Cheung 2004",
        padding: float = 0.7,
        overexposure_limit: float = 0.95,
        underexposure_limit: float = 0.8,
        rgb_images: bool = False,
        processing_steps: dict = ProcessingSteps.COLOR_CHECKER,
        image_format: str = "jpg",
        quality: int = 98,
    ) -> list[tuple[dict, list[ImageEntry]]]:
        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]
        if processing_steps is None:
            processing_steps = [
                "debayer_subsample",
                "white_balance",
                "color_correction",
                "non_linear",
                "annotate",
            ]

        return self.handle_calibration(
            "COLOR_CHECKER_DETECTION",
            {
                "detection_processing_steps": detection_processing_steps,
                "camera_ids": requested_camera_ids,
                "method": method,
                "padding": padding,
                "overexposure_limit": overexposure_limit,
                "underexposure_limit": underexposure_limit,
                "rgb": rgb_images,
                "steps": processing_steps,
                "format": image_format,
                "quality": quality,
            },
        )

    def charuco_detection(
        self,
        detection_processing_steps: dict = ProcessingSteps.CHARUCO,
        requested_camera_ids: list[str] | None = None,
        rgb_images: bool = False,
        processing_steps: dict | None = None,
        format: str = "jpg",
        quality: int = 98,
    ) -> list[tuple[dict, list[ImageEntry]]]:
        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]
        if processing_steps is None:
            processing_steps = ["debayer_subsample", "annotate"]

        return self.handle_calibration(
            "CHARUCO_DETECTION",
            {
                "detection_processing_steps": detection_processing_steps,
                "camera_ids": requested_camera_ids,
                "rgb": rgb_images,
                "steps": processing_steps,
                "format": format,
                "quality": quality,
            },
        )

    def calculate_image_brightness(
        self, requested_camera_ids: list[str] | None = None, processing_steps: dict = None
    ) -> list[tuple[dict, list[ImageEntry]]]:
        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]

        return self.handle_calibration(
            "CALCULATE_IMAGE_BRIGHTNESS",
            {
                "camera_ids": requested_camera_ids,
                "steps": processing_steps,
            },
        )
