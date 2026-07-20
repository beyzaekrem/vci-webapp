# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100


from sparrow import gibbs_wrapper as gibbs
from sparrow.image_processing.codecs import encode_images
from sparrow.mode_shared.camera_manager import CameraManager
from sparrow.modes.common import ImagePackage

### run with : python -m pytest tests/pipeline


def test_simualted_cameras(camera_manager: CameraManager) -> None:
    assert camera_manager.camera_ids == ["C7777", "C9999", "M8888"]


def test_camera_info(camera_manager: CameraManager) -> None:
    cameras = camera_manager.cameras
    cam_infos: list[dict] = camera_manager.get_camera_info()
    for info, camera in zip(cam_infos, cameras, strict=True):
        assert (
            info.get("camera_id") == camera.camera_id
        ), f"camera_id {info.get('camera_id')} from CameraInfo object match cpp.Camera {camera.camera_id}"


def test_capture(camera_manager: CameraManager) -> None:
    camera_manager.start_cameras()
    images = camera_manager.capture_images(camera_manager.camera_ids, execute_software_trigger=True)
    camera_manager.stop_cameras()
    assert all(isinstance(image, gibbs.GibbsImage) for image in images), "images should be gibbs Images"
    for image in images:
        print(image, "range: ", image.pixels.min(), image.pixels.max())
        assert image.camera_id != "undefined"
        assert image.pixel_layout != gibbs.PixelLayout.Undefined
        assert image.pixels.max() != 0
    caputred_cam_ids = [image.camera_id for image in images]
    assert set(caputred_cam_ids) == set(
        camera_manager.camera_ids
    ), f"unexpected camera_ids returned by images. Captured: {caputred_cam_ids}. Expected: {camera_manager.camera_ids} "


def test_capture_info(camera_manager: CameraManager) -> None:
    camera_manager.start_cameras()
    images = camera_manager.capture_images(execute_software_trigger=True)
    camera_manager.stop_cameras()
    images = encode_images(images, "jpg", quality=70)
    image_package = ImagePackage(camera_ids=[i.camera_id for i in images], frame_idx=1)
    image_package.add_images(images)
    d = image_package.to_dict()
    assert "image_info" in d
    for entry in d["image_info"]:
        image_type = entry["image_type"]
        assert image_type == image_type.lower()
        data_category = entry["data_category"]
        assert data_category == data_category.lower()
    image_package.to_payload()
