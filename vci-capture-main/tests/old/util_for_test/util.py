import unittest
from abc import abstractmethod

import torch
from tests.stress.old.util_for_test.save_image import ImageWriter

import sparrow.gibbs_wrapper as gibbs
from sparrow.image_processing.codecs import encode_images
from sparrow.mode_shared import CAMERA_MANAGER
from sparrow.modes.base_handler import BaseHandler

SOFTWARE_TRIGGER = True

BASE_HANDLER: BaseHandler = None


def get_or_create_base_handler() -> BaseHandler:
    global BASE_HANDLER  # noqa: PLW0603
    if BASE_HANDLER is None:
        BASE_HANDLER = BaseHandler()
    return BASE_HANDLER


# abstract test class that deals with general setUp and tearDown of a handler
class HandlerUnitTest(unittest.TestCase):
    my_handler = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.my_handler = get_or_create_base_handler()
        cls.my_handler.switch_mode(cls.switch_to_mode())
        setSoftwareTrigger(CAMERA_MANAGER.cameras, state=SOFTWARE_TRIGGER)
        cls.set_up()

    @classmethod
    @abstractmethod
    def switch_to_mode(cls) -> str:
        # switches to this mode during setUpClass
        pass

    @classmethod
    @abstractmethod
    def set_up(cls) -> None:
        # you can add your own setup code, like saving attributes
        pass

    @classmethod
    @abstractmethod
    def tear_down(cls) -> None:
        # you can add your own tear down code
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        cls.my_handler.activeHandler.on_stop()
        CAMERA_MANAGER.stop_cameras()
        setSoftwareTrigger(CAMERA_MANAGER.cameras, state=False)
        cls.tear_down()

    def tearDown(self) -> None:
        CAMERA_MANAGER.stop_cameras()


def check_image_ok(
    images: torch.tensor, camera_ids: list[str], image_format: str, shape: list[int], *, is_matte: bool
) -> tuple[list[bool], int]:
    imwriter = ImageWriter("test")
    imwriter.set_image_path("test", index_offset=True, frame_first=True)

    success_mask = []

    for image, camid in zip(images, camera_ids):
        if len(image) == 0:
            print("Image is empty")
            success_mask.append(False)
        try:
            payload = gibbs.processing.WrapTorchTensor(image)
            memory_view = payload.PyMemoryView()
            imwriter.save_image(memory_view, 0, camid, image_format, is_matte, shape)
            success_mask.append(True)
        except Exception as e:
            print(f"Image save failed {camid}, {image_format}, ismatte={is_matte}, shape={shape}, {e}")
            success_mask.append(False)
    return success_mask, len([s for s in success_mask if s])


def save_images(images: list[torch.tensor], format="jpg", *, is_matte: bool = False, camera_ids=None) -> None:
    if camera_ids is None:
        camera_ids = CAMERA_MANAGER.camera_ids
    shapes = [image.shape for image in images]
    images = [encode_images(image, format, quality=98) for image in images]
    images = [image.cpu() for image in images]
    result, cnt = check_image_ok(images, camera_ids, format, shapes, is_matte=is_matte)
    return result, cnt


def setSoftwareTrigger(cameras, *, state=True):
    for cam in cameras:
        if cam.is_running():
            raise Exception("Cameras are already running. Cannot set SoftwareTrigger Parameter")

    for cam in cameras:
        try:
            if cam.manufacturer == "Orbbec":
                if state:
                    print(f"[test] {cam.serialnumber()} -> set_trigger_source(gibbs.TriggerSource.Software)")
                    cam.set_trigger_source(gibbs.TriggerSource.Software)
                else:
                    print(f"[test] {cam.serialnumber()} -> set_trigger_source(gibbs.TriggerSource.Hardware)")
                    cam.set_trigger_source(gibbs.TriggerSource.Hardware)

        except Exception as e:
            print(f"[test] skipping trigger config on {cam.serialnumber()}: {e}")
