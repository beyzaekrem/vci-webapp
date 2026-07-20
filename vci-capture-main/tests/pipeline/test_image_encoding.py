# ruff: noqa: S101, T201  # noqa: INP001, RUF100
import io
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from gibbs import EncodedImage, GibbsImage
from sparrow.image_processing import codecs
from sparrow.image_processing.process_images import process_debayer
from sparrow.modes.common import ImagePackage
from sparrow.utils import timers

###  This file contains tests for image encoding
###  the test data is located in tests/data

### run with : python -m pytest tests/pipeline

# -- Helpers --


def save_encoded_tensor(encoded_img: EncodedImage, filename: Path) -> None:
    encoded_tensor: torch.tensor = encoded_img.data.cpu()
    with filename.open("wb") as f:
        f.write(encoded_tensor.numpy().tobytes())


# -- Fixtures --


@pytest.fixture(scope="module")
def test_output(outdata_path: Path) -> Path:
    p = outdata_path / "test_image_encoding"
    p.mkdir(exist_ok=True)
    return p


@pytest.fixture
def color_image(bayer_image: GibbsImage) -> GibbsImage:
    clone = bayer_image.clone()
    return process_debayer(clone, {"method": "interpolate"}, None)


@pytest.fixture(params=["jpg", "avif", "avif_ll", "png", "exr", "torch:uint8", "torch:float32"])
def any_image_format(request: str) -> str:
    return request.param


@pytest.fixture(params=["matte_jpg", "matte_binary", "matte_png"])
def any_matte_format(request: str) -> str:
    return request.param


@pytest.fixture(params=["png", "avif_ll", "exr"])
def lossless_format(request: str) -> str:
    return request.param


# -- tests --


def test_avif(random_color_image: GibbsImage) -> None:
    codecs.encode_image_avif(random_color_image, quality=87)


def test_avif_lossless(color_image: GibbsImage, outdata_path: Path) -> None:
    original_image = color_image.pixels.clone()
    with timers.CudaTimer("encode avif lossless"):
        encoded_image: EncodedImage = codecs.encode_image_avif_lossless(color_image)

    save_encoded_tensor(encoded_image, outdata_path / "color.avif")
    # 2. Convert encoded tensor bytes back to a PIL Image
    raw_bytes = encoded_image.data.numpy().tobytes()
    decoded_image = Image.open(io.BytesIO(raw_bytes), formats=["avif"])

    # 3. Convert back to a Torch tensor for comparison
    # Use np.array to ensure we get the raw pixel values
    result_tensor = torch.from_numpy(np.array(decoded_image)).to(torch.uint8)
    original_image = original_image.permute(1, 2, 0)

    assert (
        result_tensor.shape == original_image.shape
    ), "decoded image shape and input image shape need to match for comparison"
    original_image = (original_image.detach() * 255).to(torch.uint8)

    # 4. Check for absolute equality
    # Note: ensure shapes match (might need to permute dimensions)
    diff = torch.abs(original_image.cpu().float() - result_tensor.cpu().float())
    max_diff = torch.max(diff)
    mean_err = torch.mean(diff)

    test_text = f"encode_image_avif_lossless compression should be lossless. Mean diff: {mean_err.item()}. Max diff {max_diff.item()}. Encoded Size {len(encoded_image.data) / 1034:2f} KB"
    assert max_diff <= 3, test_text
    assert mean_err <= 0.8, test_text
    # 14 MB


def test_color_encode(color_image: GibbsImage, any_image_format: str) -> None:
    assert isinstance(color_image, GibbsImage), f"image is expected to be GibbsImage but is {type(color_image)}"
    with timers.CudaTimer(f"encode {any_image_format}") as timer:
        encoded_tensor = codecs.encode_images(color_image, any_image_format, quality=87)[0]
    print(f"\ncolor encoding {any_image_format}")
    print(f"    {timer!s}")
    print(f"    encoded Size {len(encoded_tensor.data) / 1034:2f} KB, original shape: {color_image.shape}")


def test_mono_encode(mono_image: GibbsImage, any_image_format: str) -> None:
    with timers.CudaTimer(f"encode {any_image_format}"):
        codecs.encode_images(mono_image, any_image_format, quality=87)


def test_png(random_color_image: GibbsImage) -> None:
    codecs.encode_image_png(random_color_image)


def test_capture_info_add_batch(random_color_image: GibbsImage, random_mono_image: GibbsImage) -> None:
    ip = ImagePackage(frame_idx=1, camera_ids=["C0001", "C0002"])
    encoded = codecs.encode_images([random_color_image, random_mono_image], "jpg", quality=70)
    ip.add_images(encoded)

    ip.to_payload()
