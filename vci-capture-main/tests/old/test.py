import time  # noqa: I001
import unittest


from sparrow.mode_shared import CAMERA_MANAGER, logger, MATTING, PERSISTENT_DATA, PERSISTENT_RECORD

# ruff: noqa: PT009
# ruff:noqa: TC001
from tests.stress.old.util_for_test.util import check_image_ok, setSoftwareTrigger

from sparrow.image_processing.codecs import encode_images
from sparrow.image_processing.process_images import process_images
from sparrow.image_processing.processing_steps import StepDefaults

from sparrow.modes.record_handler import RecordHandle
from sparrow.modes.replay_handler import ReplayHandler
from sparrow.modes.single_image_handler import SingleImageHandler
from sparrow.modes.mode_util import check_storage

# ruff: noqa: PT009
# ruff:noqa: TC001
from tests.stress.old.util_for_test.util import HandlerUnitTest, save_images

MONO_DIM = 2


class TestDepthCamera(HandlerUnitTest):
    @classmethod
    def switch_to_mode(cls) -> str:
        return "single"

    @classmethod
    def set_up(cls) -> None:
        cls.singlehandler: SingleImageHandler = cls.my_handler.activeHandler

    @classmethod
    def tear_down(cls):
        CAMERA_MANAGER.set_depth_mode("depth")

    def _capture(self, mode) -> None:
        CAMERA_MANAGER.set_depth_mode(mode)
        CAMERA_MANAGER.start_cameras()
        self.singlehandler.on_start()
        raw_images, entry_infos, frame_idx = self.singlehandler.capture_images()
        steps = {}

        steps_map = {
            "D*": [{"depth_scale": {"capture_max": 16384, "output_range": [2000, 2200]}}],
            "C*": [{"debayer": {"method": "subsample"}}, {"superkernel": True}],
            "M*": [{"superkernel": True}, {"hist_scale": True}],
        }

        images = process_images(raw_images, CAMERA_MANAGER.camera_ids, PERSISTENT_DATA.calibration_data, steps_map)
        result, cnt = save_images(images, format="png")

        # get actual depth from depth image:
        # depth_min = 2000  # mm
        # depth_max = 2200  # mm
        # depth_image_mm = depth_min + image * (depth_max - depth_min)

        self.assertEqual(
            cnt,
            len(CAMERA_MANAGER.camera_ids),
            f"image save failed {list(zip(CAMERA_MANAGER.camera_ids, result, strict=False))}",
        )

    def test_depth_mode(self) -> None:
        logger.info("\n---------------Test depth camera mode--------------------")
        self._capture("depth")

    def test_color_mode(self) -> None:
        logger.info("\n---------------Test color camera mode--------------------")
        self._capture("color")

    def test_mono_mode(self) -> None:
        logger.info("\n---------------Test mono camera mode--------------------")
        self._capture("mono")


class TestRingBuffer(HandlerUnitTest):

    @classmethod
    def switch_to_mode(cls) -> str:
        return "ring_buffer"

    @classmethod
    def set_up(cls) -> None:
        cls.ring_buffer_handler = cls.my_handler.activeHandler

    def test_ring_buffer(self) -> None:
        logger.info("----------------Test ring buffer--------------------")
        frame_cnt = 30

        CAMERA_MANAGER.start_cameras()
        self.my_handler.activeHandler.on_start()

        ring_buffer = self.my_handler.activeHandler.ring_buffer
        while ring_buffer.LastFrame() < frame_cnt:
            logger.info("ring_buffer.LastFrame()", ring_buffer.LastFrame())
            time.sleep(0.1)
        for camera in CAMERA_MANAGER.cameras:
            camera.perform_software_trigger()

        # save next image as example
        logger.info("save next image")
        frame_idx = ring_buffer.LastFrame()
        images = ring_buffer.GetImages(frame_idx)

        if len(images) == 0:
            self.assertNotEqual(frame_idx, 0, f"Frame {frame_idx} not available.")

        shapes = [[3, 5328, 4608] if "M" in camera_id else [3, 2664, 2304] for camera_id in CAMERA_MANAGER.camera_ids]
        result, cnt = check_image_ok(images, CAMERA_MANAGER.camera_ids, "jpg", shapes, is_matte=False)
        self.assertEqual(
            cnt, len(CAMERA_MANAGER.camera_ids), f"jpg image save failed {list(zip(CAMERA_MANAGER.camera_ids, result, strict=False))}"
        )

        logger.info("Stop")
        self.my_handler.activeHandler.on_stop()
        CAMERA_MANAGER.stop_cameras()
        logger.info("Ringbuffer test done\n")

    @unittest.skip
    def test_ring_buffer_speed(self) -> None:
        logger.info("----------------Test ring buffer speed--------------------")

        CAMERA_MANAGER.stop_cameras()
        setSoftwareTrigger(CAMERA_MANAGER.cameras, state=False)
        CAMERA_MANAGER.start_cameras()
        self.my_handler.activeHandler.on_start()

        ring_buffer = self.my_handler.activeHandler.ring_buffer
        while ring_buffer.LastFrame() < 0:
            logger.info("waiting for hardware trigger...")
            time.sleep(0.05)
        logger.info("\ncaptureing ....")

        time.sleep(2)
        logger.info("captured frames: ", ring_buffer.LastFrame())

        logger.info("Stop")
        self.my_handler.activeHandler.on_stop()
        CAMERA_MANAGER.stop_cameras()
        logger.info("Ringbuffer test done\n")

    def test_long(self) -> None:
        logger.info("----------------Test ring buffer long time--------------------")
        capture_time = 60

        CAMERA_MANAGER.stop_cameras()
        setSoftwareTrigger(CAMERA_MANAGER.cameras, state=False)
        CAMERA_MANAGER.start_cameras()
        self.my_handler.activeHandler.on_start()

        ring_buffer = self.my_handler.activeHandler.ring_buffer

        while ring_buffer.LastFrame() < 0:
            logger.info("waiting for hardware trigger...")
            time.sleep(0.05)
        logger.info("\ncaptureing ....")

        for i in range(capture_time):
            time.sleep(1)
            logger.info(f"{i+1}/{capture_time} -- {ring_buffer.LastFrame()} frames")

        # save next image as example
        logger.info("save next image")
        frame_idx = ring_buffer.LastFrame()
        images = ring_buffer.GetImages(frame_idx)

        if len(images) == 0:
            self.assertNotEqual(frame_idx, 0, f"Frame {frame_idx} not available.")

        shapes = [[3, 5328, 4608] if "M" in camera_id else [3, 2664, 2304] for camera_id in CAMERA_MANAGER.camera_ids]
        result, cnt = check_image_ok(images, CAMERA_MANAGER.camera_ids, "jpg", shapes, is_matte=False)
        self.assertEqual(
            cnt, len(CAMERA_MANAGER.camera_ids), f"jpg image save failed {list(zip(CAMERA_MANAGER.camera_ids, result, strict=False))}"
        )

        logger.info("Stop")
        self.my_handler.activeHandler.on_stop()
        CAMERA_MANAGER.stop_cameras()
        logger.info("Ringbuffer test done\n")


class TestRecordAndReplay(HandlerUnitTest):

    @classmethod
    def switch_to_mode(cls) -> str:
        return "record"

    def test_record_without_idle(self) -> None:
        logger.info("-----Test record one frame-------------")
        record_handler: RecordHandle = self.my_handler.activeHandler
        record_handler.set_recording_name("test_recording")
        CAMERA_MANAGER.start_cameras()
        record_handler.on_start()
        for camera in CAMERA_MANAGER.cameras:
            camera.perform_software_trigger()
        logger.info("record_handler.recorder.SquenceLength()", record_handler.recorder.SquenceLength())
        record_handler.on_stop()

    def test_record(self) -> None:
        logger.info("-----Test record one frame waiting before and after capture-------------")
        record_handler: RecordHandle = self.my_handler.activeHandler
        record_handler.set_recording_name("test_recording")
        CAMERA_MANAGER.start_cameras()
        record_handler.on_start()
        for camera in CAMERA_MANAGER.cameras:
            camera.perform_software_trigger()
        logger.info("record_handler.recorder.SquenceLength()", record_handler.recorder.SquenceLength())
        time.sleep(5)
        for camera in CAMERA_MANAGER.cameras:
            camera.perform_software_trigger()
        logger.info("record_handler.recorder.SquenceLength()", record_handler.recorder.SquenceLength())
        record_handler.on_stop()

    def test_replay(self) -> None:
        logger.info("----------------Test recording--------------------")
        recording_time = 10
        fps = 1
        logger.info("Record test")

        record_handler: RecordHandle = self.my_handler.activeHandler
        record_handler.set_recording_name("test_recording")

        CAMERA_MANAGER.start_cameras()
        record_handler: RecordHandle = self.my_handler.activeHandler
        check_storage()

        record_handler.on_start()  # record with timelimit
        # is currently blocking

        target_frames = fps * recording_time
        for _ in range(target_frames):
            for camera in CAMERA_MANAGER.cameras:
                camera.perform_software_trigger()
            logger.info("record_handler.recorder.SquenceLength()", record_handler.recorder.SquenceLength())
            time.sleep(1 / fps)

        record_handler.on_stop()
        recorded_frames = record_handler.recorder.SquenceLength()

        logger.info("recorded frames:", recorded_frames)
        check_storage()
        CAMERA_MANAGER.stop_cameras()
        logger.info("Record test done\n")

        logger.info("----------------Test replay images--------------------")
        self.my_handler.switch_mode("replay")
        replay_handler: ReplayHandler = self.my_handler.activeHandler
        replay_handler.set_recording_name("test_recording")
        frame = replay_handler.cache_reader.frame_count - 1
        frame = frame // 2
        logger.info(f"retriving frame {frame}")

        raw_images, entry_infos, frame_idx = replay_handler.retrieve_images(requested_frame=frame)
        steps_map = {
            "D": [],
            "C": [{"debayer": {"method": "subsample"}}, {"superkernel": True}],
            "M": [{"superkernel": True}, {"scale_hist": True}],
        }
        steps = {camera_id: steps_map[camera_id[0]] for camera_id in CAMERA_MANAGER.camera_ids}
        replay_handler.on_stop()
        images = process_images(raw_images, CAMERA_MANAGER.camera_ids, PERSISTENT_DATA.calibration_data, steps)
        shapes = [image.shape for image in images]
        images = [encode_images(image, "jpg", quality=89) for image in images]
        images = [image.cpu() for image in images]

        result, cnt = check_image_ok(images, CAMERA_MANAGER.camera_ids, "jpg", shapes, is_matte=False)
        self.assertEqual(
            cnt,
            len(CAMERA_MANAGER.camera_ids),
            f"replay jpg image save failed {list(zip(CAMERA_MANAGER.camera_ids, result, strict=False))}",
        )

    def test_replay_mattes(self) -> None:
        logger.info("----------------Test replay mattes--------------------")
        self.my_handler.switch_mode("replay")
        replay_handler: ReplayHandler = self.my_handler.activeHandler
        replay_handler.set_recording_name("test_recording")
        frame = replay_handler.cache_reader.frame_count - 1
        frame = frame // 2

        raw_images, entry_infos, frame_idx = replay_handler.retrieve_images(requested_frame=frame)
        images = process_images(
            raw_images, CAMERA_MANAGER.camera_ids, PERSISTENT_RECORD.calib_data, StepDefaults.PROCESSED
        )
        replay_handler.on_stop()

        background_images = PERSISTENT_RECORD.get_background_images(StepDefaults.PROCESSED)
        mattes = []
        for i in range(len(images)):
            images = [image[None, :, :].expand(3, -1, -1) if image.ndim == MONO_DIM else image for image in images]

            logger.info("images[i][None].shape", [image[None].shape for image in images])
            logger.info(
                "background_images[i][None].shape",
                [background_image[None].shape for background_image in background_images],
            )

            matte = MATTING.infer(images[i], background_images[i], CAMERA_MANAGER.camera_ids[i])
            mattes.append(matte)

        shapes = [matte.shape for matte in mattes]
        mattes = [encode_images(matte, "jpg", quality=89).cpu() for matte in mattes]

        result, cnt = check_image_ok(mattes, CAMERA_MANAGER.camera_ids, "jpg", shapes, is_matte=False)
        self.assertEqual(
            cnt, len(CAMERA_MANAGER.camera_ids), f"jpg image save failed {list(zip(CAMERA_MANAGER.camera_ids, result, strict=False))}"
        )


if __name__ == "__main__":
    unittest.main()
