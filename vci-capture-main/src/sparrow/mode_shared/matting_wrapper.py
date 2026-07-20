from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.modes.handler_exceptions import (
    MattingFailedError,
    MissingBackgroundError,
)
from sparrow.processing.rtmatting import Matting

MONO_NDIM = 2


@dataclass
class MattingMeta:
    net: gibbs.tasks.Matting
    dtype: torch.dtype
    color_space: Literal["rgb", "ir"]


@dataclass
class MattingLibrary:
    BACKGROUND_MATTING_V2_RGB_FLOAT16: ClassVar[str] = "BackgroundMattingV2.rgb.float16"
    VITMATTE_S_RGB_FLOAT16: ClassVar[str] = "ViTMatte-s.rgb.float16"
    CHECKPOINTS: ClassVar[tuple[str, ...]] = (
        BACKGROUND_MATTING_V2_RGB_FLOAT16,
        VITMATTE_S_RGB_FLOAT16,
    )

    def __init__(self) -> None:
        self.networks = {"default": MattingMeta(Matting(), torch.float32, "rgb")}
        for checkpoint in MattingLibrary.CHECKPOINTS:
            color_space, dtype = checkpoint.split(".")[-2:]
            dtype = getattr(torch, dtype)
            self.networks[checkpoint] = MattingMeta(
                gibbs.tasks.Matting(str(Path(__file__).parent.parent / "weights" / "matting" / f"{checkpoint}.pt")),
                dtype,
                color_space,
            )

    def infer(
        self, image: gibbs.GibbsImage, background_image: gibbs.GibbsImage, network: str = "default"
    ) -> gibbs.GibbsImage:
        """Perform image matting

        Args:
            image (gibbs.GibbsImage): (C,H,W) or (H,W) image
            background_image (gibbs.GibbsImage): (C,H,W) or (H,W) image
            camera_id (str): debug info?
            network (str, optional): Matting network to use. Defaults to "default".

        Raises:
            MattingFailedError: TODO

        Returns:
            gibbs.GibbsImage: H,W mask, with data_category = Matte
        """
        try:
            matting = self.networks[network]

            # if background_image.ndim == MONO_NDIM:
            #     background_image = background_image[None, :, :]
            # if image.ndim == MONO_NDIM:
            #     image = image[None, :, :]
            # if matting.color_space == "rgb" and background_image.shape[0] == 1:
            #     background_image = background_image.expand(3, -1, -1)
            # if matting.color_space == "rgb" and background_image.shape[0] == 1:
            #     background_image = background_image.expand(3, -1, -1)

            return matting.net.infer(image, background_image)
        except (TypeError, AssertionError, RuntimeError) as e:
            raise MattingFailedError(image, background_image, network, str(e)) from e

    def infer_multiple(
        self,
        images: list[gibbs.GibbsImage],
        backgrounds: dict[str, gibbs.GibbsImage] | list[gibbs.GibbsImage],
        network: str = "default",
    ) -> list[gibbs.GibbsImage]:
        if isinstance(backgrounds, list):
            backgrounds = {bg.camera_id for bg in backgrounds}

        missing = [i.camera_id for i in images if i.camera_id not in backgrounds]
        if len(missing) > 0:
            raise MissingBackgroundError(missing)

        ret: list[gibbs.GibbsImage] = []
        for i in images:
            bg = backgrounds.get(i.camera_id)
            if bg:
                ret.append(self.infer(i, bg, network))
        return ret


MATTING = MattingLibrary()
