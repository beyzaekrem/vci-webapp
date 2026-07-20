# noqa: INP001
from pathlib import Path

import pytest
import torch

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared import CAMERA_MANAGER
from sparrow.mode_shared.camera_manager import CameraManager
from sparrow.modes.base_handler import BaseHandler

# -- fixtures available to all files in pipeline.
# Only simulated cameras! or direct input from ./data.

# --get camera_manager or base_handler with simualted cameras.


@pytest.fixture(scope="module")
def camera_manager(base_handler: BaseHandler) -> CameraManager:
    """get camera manager with calibrated, simulated, setup cameras."""
    return CAMERA_MANAGER


@pytest.fixture(scope="module")
def base_handler(simulate_cameras, simualted_calibration) -> BaseHandler:
    """initliazed BaseHandler and sets up CameraManager to use simualted cameras and test_config"""
    return BaseHandler(server=None)


# -- test images --
@pytest.fixture(scope="module")
def mono_image_original(image_folder: Path) -> gibbs.GibbsImage:
    t_img = torch.load(image_folder / "2026_02_03_orbbec_test_001_M0006.pth", weights_only=False).cuda()
    return gibbs.GibbsImage(t_img, "test", gibbs.ImageType.Mono, gibbs.PixelLayout.Mono)


@pytest.fixture
def mono_image(mono_image_original: gibbs.GibbsImage) -> gibbs.GibbsImage:
    return mono_image_original.clone()


@pytest.fixture(scope="module")
def bayer_image_original(image_folder: Path) -> gibbs.GibbsImage:
    t_img = torch.load(image_folder / "bonn_tele_bench_003_C0037.pth", weights_only=False).cuda()
    return gibbs.GibbsImage(t_img, "test", gibbs.ImageType.Color, gibbs.PixelLayout.BGGR)


@pytest.fixture
def bayer_image(bayer_image_original: gibbs.GibbsImage) -> gibbs.GibbsImage:
    return bayer_image_original.clone()


@pytest.fixture
def random_color_image() -> gibbs.GibbsImage:
    i = gibbs.GibbsImage(torch.rand(3, 480, 640), "test", gibbs.ImageType.Color, gibbs.PixelLayout.RGB)
    return i.cuda()


@pytest.fixture
def random_mono_image() -> gibbs.GibbsImage:
    i = gibbs.GibbsImage(torch.rand(480, 640), "test", gibbs.ImageType.Mono, gibbs.PixelLayout.Mono)
    return i.cuda()
