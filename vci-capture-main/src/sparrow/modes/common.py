from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from typing_extensions import Self

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data.calibration_data import CalibrationData
from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared import MATTING
from sparrow.modes.handler_exceptions import (
    MissingBackgroundError,
)
from sparrow.modes.mode_util import filter_images, get_info
from sparrow.utils.logging import logger

IS_MOMO_DIM = 2


@dataclass
class ImagePackage:
    """A Package of EncodedImages (images, backgorunds, mattes).
    Can be send via interceptor with `to_payload`.
    """

    frame_idx: int  # index of the captured frame
    camera_ids: list[str] = field(default_factory=list)  # camera ids of requested cameras

    _images: list[gibbs.EncodedImage] = field(default_factory=list)

    extra_info: dict[str, any] = None

    def add_images(self, add_images: list[gibbs.EncodedImage]) -> None:
        """Adds EncodedImages to the Package"""
        if any(not isinstance(i, gibbs.EncodedImage) for i in add_images):
            msg = f"Capture Info only accepts EncodedImages. add_images called with: {add_images}"
            raise TypeError(msg)
        self._images.extend(add_images)
        for img in add_images:
            if img.camera_id not in self.camera_ids:
                self.camera_ids.append(img.camera_id)

    def to_dict(self) -> dict[str, any]:
        d = {
            "frame_idx": self.frame_idx,
            "camera_ids": self.camera_ids,
            "image_info": [i.to_dict() for i in self._images],
        }
        if self.extra_info is not None:
            d.update(self.extra_info)
        return d

    def to_payload(self) -> list[gibbs.interceptor.Payload]:
        """
        Turns the ImagePackage into an interceptor Payload list, that can be send over network.
        The "image_info" dict is is generated from the list of images.

        `message.Acknowledge(image_package.to_payload())`

        Returns:
            payload (list):
                A list containing:
                - 0 (json): capture info json with the following structure: {
                    "frame_idx" (int): Frame index
                    "camera_ids" (list[str]): ids of captured cameras,
                    "image_info" (list[dict]): each EncodedImage in the payload has a corresponding image_info entry
                                                of the following structure:{
                                                    "camera_id" (str): captured by this camera_id,
                                                    "data_category" (str): sematic role or purpose (image, background, matte)
                                                    "image_type" (str): the physical nature of the sensor data (color, mono, depth)
                                                    "shape" (list[int]): image shape of decoded image as tensor dimensions [(C), H, W],
                                                    "format" (str): encoding format - jpg, png, avif, etc...
                                                },
                }
                - 1-N (bytes, optional): EncodedImages - images, backgrounds, mattes. The order matches "image_info"

        """
        info = self.to_dict()
        ret = [gibbs.interceptor.Payload.FromDict(info)]
        ret.extend(gibbs.processing.WrapTorchTensor(image.data.cpu()) for image in self._images)
        return ret


CaptureFunc = Callable[[list[str], int], tuple[list[gibbs.GibbsImage], int]]


class PathParameterModel(BaseModel):
    @classmethod
    def from_message(cls, message: gibbs.interceptor.MessageIn, *, required: bool = False) -> Self:
        info = get_info(message, required=required)
        return cls.model_validate(info)


class BaseImageRequest(PathParameterModel):
    steps: dict[str, list[dict]] = Field(default_factory=lambda: StepDefaults.PROCESSED)
    camera_id: list[int] | None = None  # None = all
    format: str = "jpg"
    quality: int = Field(default=98, ge=0, le=100)


class ImageAndMatteRequest(BaseImageRequest):
    frame_idx: int = 0

    # Images
    rgb: bool = True

    # Mattes
    mattes: bool = False
    matting_network: str = MATTING.VITMATTE_S_RGB_FLOAT16
    mattes_format: str = "png"
    mattes_quality: int = Field(default=98, ge=0, le=100)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class BatchImageRequest(ImageAndMatteRequest):
    frame_idx: list[int] = Field(default_factory=list)

    def to_single_request(self, frame_idx: int) -> ImageAndMatteRequest:
        return ImageAndMatteRequest(**self.model_dump(exclude={"frame_idx"}), frame_idx=frame_idx)


def process_and_package(
    request: ImageAndMatteRequest,
    capture_function: Callable[[], tuple[list, int]],
    retrieve_backgrounds_function: Callable[[], dict[str, gibbs.GibbsImage]],
    calib_data: CalibrationData,
) -> ImagePackage:

    # get images
    raw_images, frame_idx = capture_function(request.camera_id, request.frame_idx)
    # process images
    logger.info(f"frame {frame_idx}, processing_steps {request.steps}")
    images: list[gibbs.GibbsImage] = process_images(raw_images, calib_data, request.steps)

    # prepare return info
    package = ImagePackage(frame_idx=frame_idx)
    if request.rgb:
        logger.info("encode images")
        package.add_images(encode_images(images, request.format, quality=request.quality))

    if request.mattes:
        logger.info("preparing mattes")
        background_images: dict[str, gibbs.GibbsImage] = retrieve_backgrounds_function(request.steps)
        mattes = MATTING.infer_multiple(images, background_images, request.matting_network)

        package.add_images(
            encode_images(
                mattes,
                "matte_" + request.mattes_format,
                threshold=request.threshold,
                quality=request.mattes_quality,
            )
        )
    return package


def process_and_package_backgrounds(
    request: BaseImageRequest, retrieve_background_function: Callable[[], dict[str, gibbs.GibbsImage]]
) -> ImagePackage:
    background_images: dict[str, gibbs.GibbsImage] | list[gibbs.GibbsImage] = retrieve_background_function(
        request.steps
    )
    if isinstance(background_images, dict):
        background_images = background_images.values()
    if len(background_images) == 0:
        raise MissingBackgroundError(request.camera_id)
    background_images: list[gibbs.GibbsImage] = filter_images(background_images, request.camera_id)

    encoded: list[gibbs.EncodedImage] = encode_images(background_images, request.format, quality=request.quality)
    return ImagePackage(camera_ids=[e.camera_id for e in encoded], frame_idx=-1, _images=encoded)
