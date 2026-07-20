import argparse
import os
import random
import sys
import threading
import time
import unittest
from concurrent.futures import Future

import interceptor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from controller import (  # noqa: E402
    Controller,
    FolderMode,
    ProcessingSteps,
    argmods,
    stop_on_interrupt,
    trigger_box,
)

exp = argmods.SUPER_SPEEDY_EXPOSURE
EXPOSURE = exp.exposure
GAIN = exp.gain

unittest.TestLoader.sortTestMethodsUsing = None

image_requested_cnt = 0

c: Controller = None
image_set = "capture_test"
output_folder = "Capture/Tests"
server_list = []


def main():
    parser = argparse.ArgumentParser(description="Connection test")
    parser.add_argument("-s", "--server", nargs="+", type=int, default=-1)
    global server_list
    options, args = parser.parse_known_args()
    if options.server != -1:
        server_list = options.server
    else:
        server_list = None

    global c
    with Controller(server_list) as c:
        trigger_box("off")
        unittest.main(argv=sys.argv[:1] + args)
    trigger_box("off")
    print("done")


class TestSingleMode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("----------------TestSingleMode--------------------")
        c.stop()
        mode = "single"
        print("\n\ntesting mode: ", mode)
        c.set_image_path(f"{output_folder}/{image_set}/{mode}", FolderMode.append)
        c.switch_mode(mode)
        trigger_box("off")

    @classmethod
    def tearDownClass(cls):
        c.stop()
        trigger_box("off")
        c.wait_images_transferred()

    def setUp(self):
        c.image_writer.image_saved_cnt = 0

    def tearDown(self):
        trigger_box("off")

    @unittest.skip
    def test_all_cameras_connected(self):
        print("----------------Test all cameras connected--------------------")
        self.assertEqual(
            len(c.all_camera_ids),
            len(c.system_layout.expected_cameras(["vci-" + str(server_id) for server_id in server_list])),
            "Missing cameras. ",
        )

    def test_matching_calibration_files(self):
        print("----------------Test all servers have matching calibration files--------------------")
        calib_files = [c.get_calibration_file(server_id) for server_id in range(len(c.servernames))]
        dates = [calib.get("timestamp") for calib in calib_files]
        self.assertEqual(
            len(set(dates)),
            1,
            f"servers have mismatched calibtration files. calib timestamps: {list(zip(c.servernames, dates))}",
        )
        print("All calibration files have timestamp", list(set(dates)))

    def test_set_exposure_and_gain(self):
        print("----------------Test set exposure and gain--------------------")
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)

    @unittest.expectedFailure
    def set_exposure_and_gain_when_running_fails(self):
        print("----------------Test exposure and gain when already running should fail--------------------")
        c.start()
        c.set_exposure_and_gain(EXPOSURE, GAIN)

    def test_get_calibration_file(self):
        print("----------------Test get calibration file--------------------")
        c.grab_calibration_file()

    def test_grab_background(self):
        print("----------------Test grab background--------------------")
        print("trigger sent")
        steps = [
            "debayer_malvar",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
        ]
        c.grab_background_images(image_format="jpg", steps=steps)
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))
        c.start()
        trigger_box("single")
        c.capture_images(images=True, mattes=True, steps=steps)
        trigger_box("single")
        c.capture_images(images=True, mattes=True, steps=steps)

    def test_matte(self):
        print("----------------Test single matte--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_malvar",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
        ]
        c.capture_images(images=False, steps=steps, mattes=True, mattes_format="binary")
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_matte_png(self):
        print("----------------Test singe matte in png--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]
        c.image_writer.image_saved_cnt = 0
        c.capture_images(images=False, steps=steps, mattes=True, mattes_format="png")
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_jpg(self):
        print("----------------Test single jpg--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]
        c.image_writer.image_saved_cnt = 0
        c.capture_images(image_format="jpg", steps=steps)
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_png(self):
        print("----------------Test png--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]
        c.image_writer.image_saved_cnt = 0
        c.capture_images(image_format="png", steps=steps)
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_exr(self):
        print("----------------Test exr--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "hist_scale",
        ]
        c.image_writer.image_saved_cnt = 0
        c.capture_images(image_format="exr", steps=steps)
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids) * 2)  # exr always saves images twice

    def test_torch_float32(self):
        print("----------------Test float32 (pth)--------------------")
        c.start()
        trigger_box("single")
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]
        c.image_writer.image_saved_cnt = 0
        c.capture_images(image_format="torch:float32", steps=steps)
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_request_cam_id(self):
        print("----------------Test request a single camera id repeatedly--------------------")
        c.start()
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]
        for i in range(10):
            trigger_box("single")
            c.capture_images(
                image_format="jpg",
                steps=steps,
                requested_camera_ids=[camera_ids[-1] for camera_ids in c.camera_ids_by_server],
            )
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, 10 * len(c.servernames))

    def test_cam_id_out_of_order(self):
        print("----------------Test camera_ids requested out of order--------------------")
        c.start()
        print("trigger sent")
        steps = [
            "debayer_subsample",
            "white_balance",
            "color_correction",
            "undistort",
            "non_linear",
            "hist_scale",
        ]

        time.sleep(0.1)
        trigger_box("single")
        c.capture_images(
            image_format="jpg",
            steps=steps,
            requested_camera_ids=random.sample(c.all_camera_ids, len(c.all_camera_ids)),
        )
        c.wait_images_transferred()
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    @unittest.skip
    def test_processing_gpu_memory(self):
        print("----------------Test processing gpu memory--------------------")
        c.start()
        trigger_box("on")
        for i in range(1000):
            if i % 100:
                print(f"{i}/{1000} gpu memory test")
            c.capture_images(images=False, mattes=False)

    def test_dynamic_background_processing(self):
        print("----------------Test request a single camera id repeatedly--------------------")
        c.start()
        trigger_box("on")
        print("trigger sent")
        stepsss = [ProcessingSteps.PROCESSED, ProcessingSteps.SMOL]
        for i, steps in enumerate(stepsss):
            c.capture_images(steps=steps, mattes=True)


class TestRingBuffer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)
        mode = "ring_buffer"
        print("\n\ntesting mode: ", mode)
        c.set_image_path(f"{output_folder}/{image_set}/{mode}")
        c.switch_mode(mode)

    @classmethod
    def tearDownClass(cls):
        c.stop()
        trigger_box("off")
        c.wait_images_transferred()

    def setUp(self):
        c.image_writer.image_saved_cnt = 0

    def tearDown(self):
        trigger_box("off")
        trigger_box("set_fps_30")
        c.stop()

    def _let_run(self, fps=20, capture_time=2):
        trigger_box(f"set_fps_{fps}")
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)  # exposure time will limit fps count
        c.start()
        time.sleep(1)
        print(f"let ringbuffer run for {capture_time} seconds...")
        trigger_box("on")
        time.sleep(capture_time)  # run time in seconds
        trigger_box("off")
        time.sleep(0.2)
        frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
        fps_captured = [(frames + 1) / capture_time for frames in frame_counts]
        return frame_counts, fps_captured, capture_time

    def test_invalid_range(self):
        print("----------------Test invalid range for image--------------------")
        frame_counts, fps_captured, capture_time = self._let_run()
        invalid_idx = max(frame_counts) + 1

        with self.assertRaises(interceptor.PathHandlerFailedError) as context:
            c.capture_images(frame_idx=invalid_idx)
        self.assertTrue(
            "FrameIndexOutOfBoundsError" in str(context.exception),
            "That was the wrong error.",
        )

    def test_invalid_range_mask(self):
        print("----------------Test invalid range for mask--------------------")
        frame_counts, fps_captured, capture_time = self._let_run()
        invalid_idx = max(frame_counts) + 1

        with self.assertRaises(interceptor.PathHandlerFailedError) as context:
            c.capture_mattes(frame_idx=invalid_idx)
        self.assertTrue(
            "FrameIndexOutOfBoundsError" in str(context.exception),
            "That was the wrong error.",
        )

    def test_image_transfer(self):
        print("----------------Test ring buffer image transfer--------------------")
        print("capturing test image...")
        frame_counts, fps_captured, capture_time = self._let_run()
        print(format_frame_count(c.servernames, frame_counts))

        status = c.get_status(0)
        c.capture_images(
            frame_idx=status.get("frame_idx", min(frame_counts)),
        )
        c.wait_images_transferred()
        print(f"{c.image_writer.image_saved_cnt}/{len(c.all_camera_ids) * 2} images transfered")
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_mattes_transfer(self):
        print("----------------Test ring buffer mattes transfer--------------------")
        print("capturing test masks...")
        frame_counts, fps_captured, capture_time = self._let_run()
        print(format_frame_count(c.servernames, frame_counts))

        status = c.get_status(0)
        c.capture_mattes(
            frame_idx=status.get("frame_idx", min(frame_counts)),
            mattes=True,
        )
        c.wait_images_transferred()
        print(f"{c.image_writer.image_saved_cnt}/{len(c.all_camera_ids) * 2} images transfered")
        self.assertEqual(c.image_writer.image_saved_cnt, len(c.all_camera_ids))

    def test_background_transfer(self):
        print("----------------Test ring buffer background transfer--------------------")
        c.grab_background_images()

    @unittest.skip
    def test_repeat(self):
        print("----------------test repeat--------------------")
        trigger_box(f"set_fps_{20}")
        trigger_box("off")
        for i in range(30 * 15):
            trigger_box("on")
            print(f"run {i}")
            c.start()
            time.sleep(4)

            frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
            print(format_frame_count(c.servernames, frame_counts))

            c.capture_images(
                images=False,
                mattes=False,
            )
            c.stop()
            time.sleep(2)
        trigger_box("off")

    @unittest.skip
    def test_long(self):
        fps = 15
        print("----------------Test ring buffer long runtime --------------------")
        trigger_box(f"set_fps_{fps}")
        capture_time = 180  # seconds
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)  # exposure time will limit fps count
        # c.SetFPS(fps)

        c.start()
        # also: image processing limits fps count
        time.sleep(1)
        print(f"let ringbuffer run for {capture_time} seconds...")
        trigger_box("on")

        with stop_on_interrupt():
            for i in range(capture_time):
                time.sleep(1)
                print(f"{i}/{capture_time}")
                frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
                print(format_frame_count(c.servernames, frame_counts))

        trigger_box("off")
        time.sleep(0.2)
        frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
        fps_captured = [(frames + 1) / capture_time for frames in frame_counts]
        print(format_frame_count(c.servernames, frame_counts, fps_captured))
        print(f"(expected {capture_time * fps} frames)")
        c.stop()
        time.sleep(5)
        self.assertEqual(
            len(set(frame_counts)),
            1,
            f"Ring Buffer frame_count (for {capture_time} seconds) with {fps} fps is mismatched: {list(zip(frame_counts, c.servernames))}",
        )
        self.assertEqual(
            max(frame_counts),
            capture_time * fps,
            f"Frame_count should be {capture_time * fps} when capturing with {fps} fps. "
            f"Frame_counts {list(zip(frame_counts, c.servernames))}",
        )

    def test_fps(self):
        for fps in [20, 25]:
            with self.subTest(fps):
                print(f"----------------Test ring buffer {fps} fps--------------------")
                frame_counts, fps_captured, capture_time = self._let_run(fps=fps, capture_time=5)
                print(format_frame_count(c.servernames, frame_counts, fps_captured))
                print(f"(expected {capture_time * fps} frames)")

                c.stop()
                time.sleep(5)
                self.assertEqual(
                    len(set(frame_counts)),
                    1,
                    f"Ring Buffer frame_count (for {capture_time} seconds) with {fps} fps is mismatched: {list(zip(frame_counts, c.servernames))}",
                )
                self.assertEqual(
                    max(frame_counts),
                    capture_time * fps,
                    f"Frame_count should be {capture_time * fps} when capturing with {fps} fps. "
                    f"Frame_counts {list(zip(frame_counts, c.servernames))}",
                )

    def test_live_sim(self):
        print("----------------Simulate reconstruction --------------------")
        fps = 20
        trigger_box(f"set_fps_{fps}")

        requested_cameras = []
        requested_cameras = c.camera_ids_by_server[0][:3]
        requested_cameras = [ids[0] for ids in c.camera_ids_by_server[:3]]

        stop_event = threading.Event()
        request_rate = 10
        timelimit = 30

        def request_color():
            while not stop_event.is_set():
                r = latest_common
                print(
                    f"{time.time() - start}             Send GET_IMAGES {r} ",
                    requested_cameras,
                )
                future = c.send(
                    "GET_IMAGES",
                    {"frame_idx": r, "camera_ids": requested_cameras},
                    wait=False,
                )
                future.add_done_callback(
                    lambda f, r=r, t=time.time() - start: check_for_error(f, f"             GET_IMAGES {r} callback", t)
                )
                time.sleep(1 / request_rate)

        def check_for_error(fut, message, message_send_time):
            t = time.time() - start

            responses = fut.result()
            try:
                c._connection.error_check(responses)
                print(f"{t} {message}. Took {t-message_send_time} seconds")
            except RuntimeError:

                print(f"{t} {message}. Failed. Took {t-message_send_time} seconds")
                stop_event.set()

        def handle_status_future(fut):
            responses = fut.result()
            try:
                c._connection.error_check(responses)
            except RuntimeError:
                stop_event.set()
            counts = []
            for resp in responses:
                info = resp.payload[0].ToDict()
                counts.append(info.get("frame_count"))
            if counts:
                frame_counts[:] = counts
                print(format_frame_count(c.servernames, frame_counts))
                nonlocal latest_common
                latest_common = min(frame_counts)
                print(f"{time.time() - start} latest common ", latest_common)

        request_color_thread = threading.Thread(target=request_color, daemon=True)
        capture_time = None  # seconds
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)  # exposure time will limit fps count
        # c.SetFPS(fps)

        c.start()
        # also: image processing limits fps count

        time.sleep(1)
        print(f"let ringbuffer run for {capture_time} seconds...")
        start = time.time()
        trigger_box("on")

        print("Wait 2 seconds to start running before requesting images")
        time.sleep(2)

        frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
        latest_common = min(frame_counts)

        largest_spread = 0

        try:
            with stop_on_interrupt():
                request_color_thread.start()
                while not stop_event.is_set():
                    now_time = time.time() - start

                    if timelimit is not None:
                        if now_time >= timelimit:
                            print("timelimit reached")
                            stop_event.set()

                    future: Future = c.send("STATUS", wait=False)
                    future.add_done_callback(handle_status_future)

                    spread = max(frame_counts) - latest_common
                    largest_spread = max(largest_spread, spread)
                    # print(f" frame spread : {spread}, largest {largest_spread}")
                    self.assertTrue(
                        spread < 50,
                        f"Oh no, the servers drifted appart after {now_time}! {format_frame_count(c.servernames, frame_counts)}",
                    )

                    # get_all_masks:
                    if spread < 50:
                        r = latest_common
                        print(f"{now_time}                                     Send GET_MATTES {r}")
                        future = c.send("GET_MATTES", {"frame_idx": -1}, wait=False)
                        future.add_done_callback(
                            lambda f, r=r, t=now_time: check_for_error(
                                f,
                                f"                                      GET_MATTES {r} callback",
                                t,
                            )
                        )
                    else:
                        stop_event.set()
                    # c.capture_mattes(frame_idx=latest_common)
                    time.sleep(1 / request_rate)
            trigger_box("off")
        except Exception as e:
            print(e)
        stop_event.set()
        request_color_thread.join()


class TestRecord(unittest.TestCase):
    capture_time = 10
    steps = ProcessingSteps.OVERWRITE_NO_ROTATION(ProcessingSteps.TINY_UNCALIBRATED)

    @classmethod
    def setUpClass(cls):
        c.set_image_path(f"{output_folder}/{image_set}/replay")
        trigger_box("single")

    def test_0record(self):
        for fps in [25, 30, 40, 50, 60]:  # 50 in unreachable by all
            with self.subTest(fps):
                print(f"----------------Test record with {fps} fps--------------------")
                c.stop()
                c.set_exposure_and_gain(EXPOSURE, GAIN)
                mode = "record"
                print("\n\ntesting mode: ", mode)
                c.switch_mode(mode)
                c.set_recording_name("_test")
                print(f"capturing test image for {self.capture_time} seconds ...")
                # c.SetFPS(fps)
                trigger_box(f"set_fps_{fps}")
                c.start()
                time.sleep(0.2)
                trigger_box("on")
                time.sleep(self.capture_time)
                trigger_box("off")
                time.sleep(1)
                frame_counts = [c.get_status(s).get("frame_count") for s in range(len(c.servernames))]
                fps_captured = [(frames - 1) / self.capture_time for frames in frame_counts]
                print(format_frame_count(c.servernames, frame_counts, fps_captured))
                print(f"expected frame count: {(self.capture_time * fps) + 1} for {fps} fps")
                c.stop()
                self.assertEqual(
                    len(set(frame_counts)),
                    1,
                    f"Replay frame_count (for {self.capture_time} seconds) is mismatched: {format_frame_count(c.servernames, frame_counts, fps_captured)}",
                )
                self.assertEqual(
                    max(frame_counts),
                    (self.capture_time * fps) + 1,
                    f"Frame_count should be {(self.capture_time * fps) + 1} when capturing with {fps} fps",
                )

    def test_image_transfer(self):
        print("----------------Test replay image transfer--------------------")
        c.stop()
        mode = "replay"
        print("\n\ntesting mode: ", mode)
        c.switch_mode(mode)
        c.set_recording_name("_test")
        c.capture_images(
            image_format="jpg",
            steps=self.steps,
            frame_idx=0,
            mattes=True,
            mattes_format="binary",
        )
        c.wait_images_transferred()


class TestCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c.stop()
        c.set_exposure_and_gain(EXPOSURE, GAIN)
        mode = "calibration"
        print("\n\ntesting mode: ", mode)
        c.set_image_path(f"{output_folder}/{image_set}/{mode}")
        c.switch_mode(mode)

    @classmethod
    def tearDownClass(cls):
        c.stop()
        trigger_box("off")
        c.wait_images_transferred()

    def setUp(self):
        c.image_writer.image_saved_cnt = 0

    def tearDown(self):
        trigger_box("off")
        trigger_box("set_fps_30")
        c.stop()

    def test_color_checker_detection(self):
        print("----------------Test color checker detection--------------------")
        c.start()
        trigger_box("single")
        c.color_checker_detection(overexposure_limit=0.99, underexposure_limit=0.7, rgb_images=False)


def format_frame_count(servernames, frame_count, fpss=None):
    out = "Frame Count"
    for val in set(frame_count):
        servers = [server for server, server_val in zip(servernames, frame_count) if server_val == val]
        if fpss is not None:
            fps = fpss[servernames.index(servers[0])]
            out += f"\n{val} frames, {fps} fps - {servers}({len(servers)})"
        else:
            out += f"\n{val} frames - {servers}({len(servers)})"
    return out


if __name__ == "__main__":
    main()
