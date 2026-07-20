import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import Imath
import numpy as np
import OpenEXR
import torch
import torchvision
from PIL import Image as PIL_Image

import sparrow.gibbs_wrapper as gibbs

# region encode decorator: dict[format] = (encoidng_function, run_in_threadpool)
encode_functions: dict[str, tuple[callable, bool]] = {}


def encode(*image_formats: tuple[str], thread_pool: bool = False) -> callable:
    def decorator(f: callable) -> callable:
        for image_format in image_formats:
            if image_format in encode_functions:
                msg = f"format {image_format} is already implemented by function {encode_functions[image_format]}"
                raise RuntimeError(msg)
            encode_functions[image_format] = (f, thread_pool)
        return f

    return decorator


# endregion


def fix_channels(image: gibbs.GibbsImage) -> None:
    # shape (C,) H, W
    # with C in {1, 3, 4}
    # dtype float32
    if image.dtype != torch.float32:
        msg = f"Wrong image dtype, got {image.dtype} but only torch.float32 is supported"
        raise ValueError(msg)
    if image.ndim not in {3, 2}:
        msg = f"Wrong image dimensions, got {image.ndim} but only 2 and 3 are supported"
        raise ValueError(msg)

    if image.ndim == 2:  # noqa: PLR2004
        image.pixels = image.pixels[None, :, :]
    if image.shape[0] not in [1, 3, 4]:
        msg = f"Wrong image shape, got {image.shape[0]} channels but only 1, 3, and 4 are supported"
        raise ValueError(msg)


def to_pil_image(image: gibbs.GibbsImage) -> PIL_Image:
    fix_channels(image)
    # To uint8
    image_np = (image.pixels.detach() * 255).to(torch.uint8).cpu().numpy()

    # Mode and Arrange
    channels = image.shape[0]
    if channels == 1:
        image_np = image_np.squeeze(0)
        mode = "L"  # Grayscale mode
    else:
        image_np = np.transpose(image_np, (1, 2, 0))
        mode = "RGB" if channels == 3 else "RGBA"  # noqa: PLR2004

    # Create an image using PIL and save to a bytes buffer
    return PIL_Image.fromarray(image_np, mode=mode)


@encode("avif", "matte_avif", thread_pool=True)
def encode_image_avif(image: gibbs.GibbsImage, quality: int, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    assert isinstance(image, gibbs.GibbsImage), "Image is not GibbsImage"
    p_image: PIL_Image = to_pil_image(image)
    buffer = io.BytesIO()
    p_image.save(buffer, format="AVIF", codec="aom", quality=quality)

    encoded_pixels = torch.frombuffer(bytearray(buffer.getvalue()), dtype=torch.uint8)
    return gibbs.EncodedImage(encoded_pixels, image, "avif")


@encode("avif_ll", "matte_avif_ll", thread_pool=True)
def encode_image_avif_lossless(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    p_image: PIL_Image = to_pil_image(image)
    buffer = io.BytesIO()
    p_image.save(
        buffer,
        format="AVIF",
        codec="aom",
        quality=100,
        subsampling="4:4:4",
    )
    # ignores lossless argument.

    encoded_pixels = torch.frombuffer(bytearray(buffer.getvalue()), dtype=torch.uint8)
    return gibbs.EncodedImage(encoded_pixels, image, "avif_ll")


@encode("exr", "matte_exr")
def encode_image_exr(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    fix_channels(image)
    _, height, width = image.shape

    # Make header
    image_np = image.pixels.detach().cpu().numpy()
    if image.shape[0] == 1:
        channel_names = ["X"]
    elif image.shape[0] == 3:  # noqa: PLR2004
        channel_names = ["R", "G", "B"]
    elif image.shape[0] == 4:  # noqa: PLR2004
        channel_names = ["R", "G", "B", "A"]
    channels = {c: image_np[i, :, :].tobytes() for i, c in enumerate(channel_names)}
    header = OpenEXR.Header(width, height)
    header["channels"] = {c: Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT)) for c in channel_names}
    # See https://openexr.com/en/latest/TechnicalIntroduction.html#data-compression
    # NO_COMPRESSION, RLE_COMPRESSION, ZIPS_COMPRESSION, ZIP_COMPRESSION, PIZ_COMPRESSION,
    # PXR24_COMPRESSION, B44_COMPRESSION, B44A_COMPRESSION, DWAA_COMPRESSION, DWAB_COMPRESSION
    header["compression"] = Imath.Compression(Imath.Compression.PIZ_COMPRESSION)

    # Write to shared memory file and load as np array
    shm_file = Path("/dev/shm/stupid_openexr_cannot_write_to_ram.exr")  # noqa: S108
    exr_file = OpenEXR.OutputFile(str(shm_file), header)
    exr_file.writePixels(channels)
    exr_file.close()
    byte_array = np.fromfile(shm_file, np.uint8)
    shm_file.unlink()
    encoded_pixels = torch.from_numpy(byte_array)
    return gibbs.EncodedImage(encoded_pixels, image, "exr")


@encode("png", "matte_png", thread_pool=True)
def encode_image_png(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    p_image: PIL_Image = to_pil_image(image)
    buffer = io.BytesIO()
    p_image.save(buffer, format="PNG")

    encoded_pixels = torch.frombuffer(bytearray(buffer.getvalue()), dtype=torch.uint8)
    return gibbs.EncodedImage(encoded_pixels, image, "png")


@encode("png_2", thread_pool=True)
def encode_image_png2(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    p_image: PIL_Image = to_pil_image(image)
    torchvision.io.encode_png(image)
    buffer = io.BytesIO()
    p_image.save(buffer, format="PNG")

    encp = torch.frombuffer(bytearray(buffer.getvalue()), dtype=torch.uint8)
    return gibbs.EncodedImage(encp, image, "png")


@encode("matte_binary")
def encode_matte_jpg(matte: gibbs.GibbsImage, threshold: float, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    return gibbs.processing.encode_mask(matte, threshold)


@encode("jpg", "matte_jpg")
def encode_jpg(image: gibbs.GibbsImage, quality: int, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    # Mono to RGB if we are given a mono image
    fix_channels(image)
    if image.shape[0] == 1:
        image.pixels = image.pixels.expand(3, -1, -1)
    # torch to jpg
    image.pixels = (255 * image.pixels).clamp(0, 255).to(torch.uint8).contiguous()
    return gibbs.processing.encode_jpg(image, quality)


@encode("torch:uint8")
def encode_torch_uint8(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    encp = (255 * image.pixels).clamp(0, 255).to(torch.uint8)
    return gibbs.EncodedImage(encp, image, "torch:uint8")


@encode("torch:float32")
def encode_torch_float32(image: gibbs.GibbsImage, *args: tuple, **kwargs: dict) -> gibbs.EncodedImage:
    encp = image.pixels.to(torch.float32)
    return gibbs.EncodedImage(encp, image, "torch:float32")


executor = ThreadPoolExecutor(max_workers=12)


def encode_images(
    images: gibbs.GibbsImage | list[gibbs.GibbsImage],
    enc_format: str,
    force_threadpool: bool | None = None,
    *args: tuple,
    **kwargs: dict,
) -> gibbs.EncodedImage | list[gibbs.EncodedImage]:
    """Encodes a CUDA image with the given encoding_format.
    The resulting image is still a torch tensor and may be saved as-is to file:

    ```python
    encoded = encode_image(images, "png", quality=100).cpu()
    with file_name.open("wb") as f:
        f.write(encoded.numpy().tobytes())
    ```

    Args:
        images (torch.Tensor): input images to be encoded. On CUDA device.
        enc_format (str): encoding format. (avif, avif_ll, exr, png, matte_binary, jpg, torch:uint8, troch_float:32)

    Raises:
        KeyError: unknown encoding format.

    Returns:
        torch.Tensor: encoded torch tensor. On CUDA device.
    """
    if enc_format not in encode_functions:
        msg = f"Invalid Encoding format {enc_format}"
        raise KeyError(msg)
    enc_func, run_in_threadpool = encode_functions[enc_format]
    if isinstance(images, gibbs.GibbsImage):
        images = [images]

    use_threadpool = run_in_threadpool
    if force_threadpool is not None:
        use_threadpool = force_threadpool

    if use_threadpool := False:
        # run in threadpool - faster for cpu based (Pillow) encoding (png, avif)
        return list(executor.map(lambda img: enc_func(img, *args, **kwargs), images))

    # run sequential - faster for gpu encoding (jpg)
    print("enc_format", format, *args, kwargs)
    return [enc_func(image, *args, **kwargs) for image in images]
