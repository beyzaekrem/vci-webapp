# noqa: INP001, RUF100

import pathlib as Path

import pytest

import sparrow.gibbs_wrapper as gibbs
from sparrow.calibration_data.background_images import BackgroundImages
from sparrow.calibration_data.camera_parameters import EMPTY_CAMERA_PARAMETERS
from sparrow.image_processing.process_images import process_debayer, process_images
from sparrow.image_processing.processing_steps import StepDefaults
from sparrow.mode_shared.persistent import PersistentData

###  This file contains tests for image encoding
###  the test data is located in tests/data


### run with : python -m pytest tests/pipeline
@pytest.fixture(params=StepDefaults.get_all().values(), ids=StepDefaults.get_all().keys())
def any_default_processing_step(request: dict) -> dict:
    return request.param


@pytest.fixture(params=[gibbs.PixelLayout.BGGR, gibbs.PixelLayout.RGGB, gibbs.PixelLayout.GBRG, gibbs.PixelLayout.GRBG])
def any_bayer_pixel_layout(request) -> gibbs.PixelLayout:
    return request.param


@pytest.fixture(params=["subsample", "malvar", "interpolate"])
def any_debayer_method(request) -> str:
    return request.param


def test_color_processing(
    bayer_image: gibbs.GibbsImage, any_default_processing_step: dict, fully_calibrated: PersistentData
) -> None:
    print(any_default_processing_step)
    bayer_image.camera_id = "C9999"
    process_images([bayer_image], fully_calibrated.calibration_data, any_default_processing_step)


def test_debayer_smol(
    bayer_image: gibbs.GibbsImage, any_bayer_pixel_layout: gibbs.PixelLayout, any_debayer_method: str
):
    image = bayer_image
    image.pixel_layout = any_bayer_pixel_layout

    assert image.is_bayer(), "input image should be bayer for this test"

    result = process_debayer(image, {"method": any_debayer_method}, EMPTY_CAMERA_PARAMETERS)

    assert result.is_rgb(), "image should be rgb after debayer step is applied"
    assert image.is_rgb(), "input image should be rgb after debayer"
    assert image == result, "the image should be muated in place."


def test_debayer(bayer_image: gibbs.GibbsImage, any_bayer_pixel_layout: gibbs.PixelLayout, any_debayer_method: str):
    image = bayer_image
    image.pixel_layout = any_bayer_pixel_layout

    assert image.is_bayer(), "input image should be bayer for this test"

    image.camera_id = "C9999"
    result = process_images(
        [image], None, {"C*": [{"debayer": {"method": any_debayer_method}}, {"rotate": {"enabled": False}}]}
    )[0]

    assert result.is_rgb(), "image should be rgb after debayer step is applied"
    assert image.is_rgb(), "input image should be rgb after debayer"
    assert image == result, "the image should be muated in place."


def test_wrong_order(bayer_image: gibbs.GibbsImage) -> None:

    ERROR = {
        "C*": [
            {"superkernel": {}},
        ],
        "D*": [],
        "M*": [],
    }


def test_background(fully_calibrated: PersistentData) -> None:
    fully_calibrated.get_background_images(StepDefaults.COLOR_PRETTY)


def test_background_save_and_load(bayer_image: gibbs.GibbsImage, tmp_path: Path) -> None:
    bayer_image.data_category = gibbs.DataCategory.Background
    backgrounds = BackgroundImages()
    backgrounds.set_background_images([bayer_image])
    backgrounds.save(tmp_path / "<camera_id>_bg_test.pth")

    assert len(backgrounds.raw_background_images) == 1

    loaded = BackgroundImages()
    loaded.load(backgrounds.camera_ids, tmp_path / "<camera_id>_bg_test.pth")

    assert len(loaded.raw_background_images) == 1
