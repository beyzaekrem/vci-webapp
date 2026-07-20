from __future__ import annotations

from pathlib import Path

import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data.calibration_data import CalibrationData
from sparrow.calibration_data.camera_parameters import CameraParameters
from sparrow.gibbs_wrapper import interceptor
from sparrow.image_processing.process_images import process_images
from sparrow.modes.handler_exceptions import MissingBackgroundError
from sparrow.utils import logger

IS_MONO_DIM = 2


class BackgroundImages:

    def __init__(self) -> None:
        self._raw_background_images: dict[str, gibbs.GibbsImage]

        # cache for processed images.
        self._processed_background_images: dict[str, gibbs.GibbsImage] = {}
        self._background_processing_steps: list[str] | dict | None = None

    @property
    def raw_background_images(self) -> dict[str, gibbs.GibbsImage]:
        # proteting raw_background_images from direct setting operations
        # that would invalidate processed images cache.
        return self._raw_background_images

    @property
    def camera_ids(self) -> list[str]:
        return list(self._raw_background_images.keys())

    @staticmethod
    def resolve_camera_id(image_path: Path | str, camera_id: str) -> str:
        return str(image_path).replace("<camera_id>", camera_id)

    def load(self, camera_ids: list[str], image_path: str) -> None:
        raw_background_images = {}
        camera_ids = camera_ids or []
        for camera_id in camera_ids:
            image_path_of_camera = self.resolve_camera_id(image_path, camera_id)
            img = None

            try:
                # try to load full GibbsImage Archive pth file
                logger.debug(f"BackgroundImages.load: GibbsImage load_from_pth {camera_id}")
                img: gibbs.GibbsImage = gibbs.GibbsImage.load_from_pth(image_path_of_camera)
                img.data_category = gibbs.DataCategory.Background
            except RuntimeError as e:
                if "PytorchStreamReader failed locating file constants.pkl" in str(e):
                    pass  # its not an archive file that could be loaded like this.
                    # thats fine, its probably just a normal tensor pth, that we can load and wrap.
                elif "Not a directory" in str(e) or "No such file or directory" in str(e):
                    pass  # FileNotFoundError, NotADirectoryError
                else:
                    msg = f"Failed to load gibbsImage from archive file: {image_path_of_camera}: {e}"
                    raise RuntimeError(msg) from e  # some unexpected error when opening the pth.

            try:
                if img is None:
                    # if that fails, try to load tensor pth.
                    logger.debug(f"BackgroundImages.load: GibbsImage load_tensor_as_background {camera_id}")
                    img = self.load_tensor_as_background(image_path, camera_id)
                    logger.info(f"Old-style tensor background loaded and wrapped for {camera_id}")
            except (FileNotFoundError, NotADirectoryError):
                pass

            if img:
                img = img.cuda()
                raw_background_images[camera_id] = img
            else:
                logger.warning(f"No background found for {camera_id}")

        logger.info(f"Backgrounds loaded for {list(raw_background_images.keys())} from {image_path}")
        self.set_background_images(raw_background_images)

    @staticmethod
    def load_tensor_as_background(image_path: Path | str, camera_id: str) -> gibbs.GibbsImage | None:
        image_path_of_camera = BackgroundImages.resolve_camera_id(image_path, camera_id)
        loaded = torch.load(image_path_of_camera, weights_only=False)
        if isinstance(loaded, torch.Tensor):
            pix_l = gibbs.PixelLayout.BGGR
            img_t = gibbs.ImageType.Color
            if camera_id[0] == "M":
                pix_l = gibbs.PixelLayout.Mono
                img_t = gibbs.ImageType.Mono
            if camera_id[0] == "D":
                pix_l = gibbs.PixelLayout.Mono if loaded.ndim == 2 else gibbs.PixelLayout.RGB  # noqa: PLR2004
                img_t = gibbs.ImageType.Depth if loaded.ndim == 2 else gibbs.ImageType.Color  # noqa: PLR2004
            img = gibbs.GibbsImage(loaded, camera_id, img_t, pix_l)
            img.data_category = gibbs.DataCategory.Background
            return img
        return None

    def get_background_images(
        self, processing_steps: dict[str : list[dict]], calib_data: CalibrationData
    ) -> dict[str, gibbs.GibbsImage]:
        """
        Returns the background images processed with the requested steps.
        The backgrounds are cached. Requesting the same steps again, returns the background from cache.
        """
        if self._check_processing_needed(processing_steps):
            self._process_backgrounds(processing_steps, calib_data)
            self._background_processing_steps = processing_steps
        return self._processed_background_images

    def check_missing_backgrounds(self, camera_ids: list[str]) -> None:
        """Checks if the requested camera_ids have a background image.

        Raises:
            MissingBackgroundError: _description_
        """
        missing = [cam_id for cam_id in camera_ids if cam_id not in self._raw_background_images]
        if len(missing) > 0:
            raise MissingBackgroundError(missing)

    def save(
        self,
        image_path: str | Path,
    ) -> None:
        for camera_id, raw_image in self.raw_background_images.items():
            background_for_camera_path = str(image_path).replace("<camera_id>", camera_id)
            Path(image_path).parent.mkdir(exist_ok=True, parents=True)
            raw_image.save_to_pth(background_for_camera_path)

    def set_background_images(
        self, new_raw_background_images: dict[str, gibbs.GibbsImage] | list[gibbs.GibbsImage]
    ) -> None:
        """Sets raw backgorund images and clears processed images cache."""
        if isinstance(new_raw_background_images, list):
            new_raw_background_images = {i.camera_id: i for i in new_raw_background_images}
        # assign DataCategory Background.
        for image in new_raw_background_images.values():
            image.data_category = gibbs.DataCategory.Background

        self._raw_background_images = new_raw_background_images
        self.clear_cache()

    def clear_cache(self) -> None:
        self._processed_background_images = {}
        self._background_processing_steps = None

    def _check_processing_needed(self, new_processing_steps: dict[str, list[dict]]) -> bool:
        if (  # we dont have processed backgrounds and arent given processing steps
            self._background_processing_steps is None and new_processing_steps is None
        ):  # this happens if the user calls Get_Background_Images before calling Capture
            msg = "No processed backgrounds available. Please define steps."
            raise interceptor.WrongPayloadError(msg)

        if new_processing_steps is None:
            return False  # returns background with previous processing if no new processing_steps are given
        if self._background_processing_steps is None:
            return True  # we don't have processed backgrounds so theys need to be processed

        # lastly, we need to process again, if the new_processing_steps are not the same as the previous ones
        return new_processing_steps != self._background_processing_steps

    def _process_backgrounds(
        self,
        processing_steps: dict[str, list[dict]],
        calib_data: dict[str, CameraParameters],
    ) -> None:

        # re-process the backgrounds with different processing steps
        background_images: list[gibbs.GibbsImage] = [r.clone() for r in self._raw_background_images.values()]
        process_images(background_images, calib_data, processing_steps)
        for img in background_images:
            if img.ndim == IS_MONO_DIM:
                img.pixels = img.pixels[None, :, :].expand(3, -1, -1)
        self._processed_background_images = {i.camera_id: i for i in background_images}
