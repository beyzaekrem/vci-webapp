# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100


import pytest

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared.matting_wrapper import MattingLibrary


@pytest.fixture(scope="module")
def matting() -> MattingLibrary:
    return MattingLibrary()


def test_color_matting(random_color_image: gibbs.GibbsImage, matting: MattingLibrary) -> None:
    bg = random_color_image.clone()
    matte = matting.infer(random_color_image, bg)


def test_mono_matting(random_mono_image: gibbs.GibbsImage, matting: MattingLibrary) -> None:
    bg = random_mono_image.clone()
    matte = matting.infer(random_mono_image, bg)
