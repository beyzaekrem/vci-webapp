import time

# import torch_tensorrt
# pip install torch torch-tensorrt tensorrt --extra-index-url https://download.pytorch.org/whl/cu124
# pip uninstall torchvision
# pip install torchvision
# https://pytorch.org/TensorRT/getting_started/installation.html#installation
import gibbs_wrapper as gibbs
from modes.base_handler import BaseHandler
from modes.util import load_background_images

if __name__ == "__main__":
    basehandler = BaseHandler()
    cameras: list[gibbs.Camera] = basehandler.cameras
    camera_ids = basehandler.camera_ids
    calib_data = basehandler.calib_data

    # net = basehandler.net
    # net = net.eval()
    # net = net.half()
    # net = torch.jit.script(net)
    # net = torch.jit.optimize_for_inference(net)
    # # input_shape = torch_tensorrt.Input(
    # #     min_shape=(1, 3, 2304, 2664),
    # #     opt_shape=(1, 3, 2304, 2664),
    # #     max_shape=(1, 3, 4608, 5328),
    # #     dtype=torch.float32,
    # # )
    # # net = torch_tensorrt.compile(
    # #     net,
    # #     ir="torchscript",
    # #     inputs=[input_shape,input_shape],
    # #     truncate_long_and_double=True,
    # # )
    # net.save("BackgroundMattingV2.pt")
    # exit(0)

    net = gibbs.tasks.Matting("./src/sparrow/weights/matting/BackgroundMattingV2.float16.pt")
    # fg = torch.rand((1, 3, 1024, 1024)).cuda()
    # bg = fg.clone()
    # fg[:,:,50:55,100:105] = 1
    # out = matting.forward(fg, bg)
    # print(out.mask.shape)

    # exit(0)

    software_trigger_fps = 25

    uncalibrated_cameras = [cam_id for cam_id in camera_ids if cam_id not in calib_data]
    if len(uncalibrated_cameras) > 0:
        raise RuntimeError(f"Missing calibration data for {uncalibrated_cameras}")
    calib: list[dict] = [calib_data[cam_id] for cam_id in camera_ids]
    is_color = [c.isColor for c in calib]
    calib = [[c.wb_coefficients, c.color_correction_matrix, c.intrinsic_matrix, c.distortion_coeffs] for c in calib]

    background_images = load_background_images(camera_ids, calib_data, ["debayer_subsample", "superkernel"])

    missing_background_images = [cam_id for cam_id, bg in zip(camera_ids, background_images) if bg is None]
    if len(missing_background_images) > 0:
        raise RuntimeError(f"Missing background image for {missing_background_images}")
    print("shapes background_images", [gb.shape for gb in background_images])

    ring_buffer = gibbs.tasks.RingBuffer(cameras, calib, is_color, net, background_images, 0.5, software_trigger_fps)

    for camera in cameras:
        camera.stop()
        camera.set_parameter_int("exposure", 1 * 1000)
        camera.set_parameter_int("trigger_source", 3)  # 3=XI_TRG_SOFTWARE
        # camera.set_parameter_int("trigger_source", 0) # 0=XI_TRG_OFF
        # camera.set_parameter_int("acq_timing_mode", 2) # 2=XI_ACQ_TIMING_MODE_FRAME_RATE_LIMIT
        # camera.set_parameter_float("framerate", software_trigger_fps)
        camera.allocate_buffer()
    print("Cameras Ready")
    time.sleep(1)

    ring_buffer.Run()
    print("Running")

    for camera in cameras:
        camera.start()
    print("Cameras Started")

    for i in range(60):
        time.sleep(1)
        print(ring_buffer.LastFrame())

    ring_buffer.Stop()
    for camera in cameras:
        camera.stop()
    print("Stopped")
