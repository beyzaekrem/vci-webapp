from ..output_writers.image_writer import ImageEntry
from ..processing_steps import ProcessingSteps
from .base import ControllerComponent


class CaptureModule(ControllerComponent):

    def take_background_image(self) -> None:
        """The servers capture an image per camera and
        save it (unprocessed) as new background image to the servers' persistent storage.

        Calling grab_background_images will give you new new background.

        The backgrounds are used for the masks (foreground/background segmentation).

        **server mode:** single
        **API endpoint:** TAKE_BACKGROUND_IMAGE.
        """
        self.ui.info("Taking background images...")
        self.send("TAKE_BACKGROUND_IMAGE")
        self.ui.info("Background images done")

    def skip_next_frame(self) -> None:
        """The next frame is ignored.

        **server mode:** single, record
        **API endpoint:** SKIP_NEXT_FRAME
        """
        self.send("SKIP_NEXT_FRAME")

    def set_skip_frames(self, n: int = 1) -> None:
        """The next N frames are ignored.

        **server mode:** single, record
        **API endpoint:** SKIP_NEXT_FRAME

        Args:
            n (int, optional): number of frames to skip. Defaults to 1.
        """
        self.send("SET_SKIP_FRAMES", {"skip": n})

    def handle_capture(
        self, path: str, parameters: dict | None = None, *, add_to_preview_writer: bool = False
    ) -> list[ImageEntry]:
        """Polls API endpoint (path+parameters) from connected servers, and passes the responses to the build in image_writer.
        The images may be saved and are returned as ImageEntires.

        If add_to_preview_writer is True, the image_entries are passed to the preview_writer as well.

        Args:
            path (str): API endpoint.
            parameters (dict, optional): optional parameters for the API endpoint.
            add_to_preview_writer (bool, optional): If True, passes ImageEntries to preview_writer. Defaults to False.

        Returns:
            list[ImageEntry]: resulting ImageEntries.
        """
        list_of_lists: list[list[ImageEntry]] = self.send(
            path, parameters=parameters, callback=self.image_writer.save_images_from_response
        )
        # flatten list.
        image_entries = [image_entry for callback_repsonse in list_of_lists for image_entry in callback_repsonse]
        if add_to_preview_writer:
            self.preview_writer.submit_images(image_entries)

        return image_entries

    def capture_images(
        self,
        steps: dict = ProcessingSteps.PROCESSED,
        requested_camera_ids: list[int] | None = None,
        frame_idx: int = 0,
        images: bool = True,
        image_format: str = "jpg",
        quality: int = 98,
        mattes: bool = False,
        mattes_format: str = "png",
        mattes_quality: int = 98,
        threshold: float = 0.5,
        invalid_ok: bool = False,
    ) -> list[ImageEntry]:

        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]

        return self.handle_capture(
            "GET_IMAGES",
            {
                "steps": steps,
                "rgb": images,
                "camera_ids": requested_camera_ids,
                "format": image_format,
                "quality": quality,
                "mattes": mattes,
                "mattes_format": mattes_format,
                "mattes_quality": mattes_quality,
                "frame_idx": frame_idx,
                "threshold": threshold,
            },
            add_to_preview_writer=True,
        )

    def grab_background_images(
        self,
        steps: dict | None = None,  # with none, it will give us the last processing used when creating mattes
        requested_camera_ids: list[str] | None = None,
        image_format: str = "jpg",
        quality: int = 98,
        invalid_ok: bool = False,
    ) -> list[ImageEntry]:

        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]

        return self.handle_capture(
            "GET_BACKGROUND_IMAGE",
            parameters={
                "format": image_format,
                "steps": steps,
                "quality": quality,
                "camera_ids": requested_camera_ids,
            },
        )

    def capture_mattes(
        self,
        processing_steps: dict = ProcessingSteps.PROCESSED,
        camera_ids: list[str] | None = None,
        frame_idx: int = 0,
        images: bool = False,
        image_format: str = "jpg",
        quality: int = 98,
        mattes: bool = True,
        mattes_format: str = "png",
        mattes_quality: int = 98,
    ) -> list[ImageEntry]:
        return self.capture_images(
            processing_steps,
            camera_ids,
            frame_idx,
            images,
            image_format,
            quality,
            mattes,
            mattes_format,
            mattes_quality,
        )

    def capture_mean(
        self,
        steps: dict = ProcessingSteps.PROCESSED,
        requested_camera_ids: list[str] | None = None,
        image_cnt: int | None = None,
        images: bool = True,
        image_format: str = "jpg",
        quality: int = 98,
    ) -> list[ImageEntry]:
        if isinstance(requested_camera_ids, str):
            requested_camera_ids = [requested_camera_ids]

        return self.handle_capture(
            "GET_MEAN_IMAGE",
            {
                "steps": steps,
                "rgb": images,
                "camera_ids": requested_camera_ids,
                "format": image_format,
                "quality": quality,
                "image_cnt": image_cnt,
            },
        )
