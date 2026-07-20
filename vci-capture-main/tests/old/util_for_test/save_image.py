import builtins
import io
import json
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
import torchvision
from natsort import natsorted
from PIL import Image

# region save decorator
image_format_functions = {}


def save(image_format, **options):
    def decorator(f):
        if image_format in image_format_functions:
            raise RuntimeError(
                f"image format {image_format} is already implemented by function {image_format_functions[image_format]}"
            )
        image_format_functions[image_format] = f
        return f

    return decorator


# endregion


class ImageWriter:

    def __init__(self, server_names):
        self.enabled = False

        self.framecount = {}
        self.failure_cnt = {}
        self.silent = False
        self.output_folder = "/tmp/capture"
        self.frame_first = False

        self.thread_pool = ThreadPoolExecutor(max_workers=30)
        self.lock = threading.Lock()
        self.image_saved_cnt = 0

        self.save_image_offset = 0
        self.image_name_suffix = ""

        for server_name in server_names:
            self.framecount[server_name] = {"GET_IMAGES": 0, "GET_MATTES": 0}
            self.failure_cnt[server_name] = 0

    def save_images_from_response(self, response, servername, camera_ids):
        futures_with_info = []
        if len(response.payload) > 0:
            frame_info = response.payload[0].ToDict()
            frame_idx = frame_info["frame_idx"]
            self.mutable_print(
                f"Recieved Image. {frame_idx} {servername}. payload length {len(response.payload)}. frame-info\n{frame_info}"
            )
            self.framecount[servername]["frame_idx"] = frame_idx
            image_info = frame_info.get("image_info", [{} for _ in range(len(frame_info["camera_ids"]))])
            for idx, info in enumerate(image_info, 1):
                cam_id = info.get("camera_id")
                if cam_id is None:
                    cam_id = camera_ids[(idx - 1) % len(camera_ids)]
                shape = info.get("shape", [])
                is_matte = info.get("is_matte", False)
                image_format = info.get("format", "jpg")
                if is_matte:
                    image_format = "matte_" + image_format
                memory_view = response.payload[idx].PyMemoryView()
                if len(memory_view) == 1:
                    self.mutable_print(f"Frame is empty {cam_id} {servername}")
                    futures_with_info.append((None, cam_id, frame_idx))
                    continue
                self.mutable_print("Save image", frame_idx, cam_id, idx, "...")
                # future = self.save_image(memory_view, frame_idx, cam_id, image_format, is_matte, shape)
                future = self.thread_pool.submit(
                    self.save_image, memory_view, frame_idx, cam_id, image_format, is_matte, shape
                )
                futures_with_info.append((future, cam_id, frame_idx))
        else:
            self.mutable_print("     Payload is empty (｡•́︿•̀｡)", response.path, servername, camera_ids)
            self.failure_cnt[servername] += len(camera_ids)
            self.mutable_print(
                "     failure_cnt:",
                [self.failure_cnt[servername] for servername in self.failure_cnt if self.failure_cnt[servername] > 0],
            )
            futures_with_info = [(None, cam_id, -1) for cam_id in camera_ids]
        return futures_with_info  # (future(image), cam_id, frame_idx)

    def wait_images_transferred(self, futures_with_info=None):
        if futures_with_info is None:
            print("wait all images transfered")
            self.thread_pool.shutdown(wait=True)
            self.thread_pool = ThreadPoolExecutor(max_workers=30)
            return None

        images_with_info = []
        for future, cam_id, frame_idx in futures_with_info:
            if future is not None:
                images_with_info.append((future.result(), cam_id, frame_idx))
            # images_with_info.append((saved_image, cam_id, frame_idx))
        return images_with_info

    def print_info(self, expected_cnt):
        print(f"Images saved {self.image_saved_cnt}/{expected_cnt}.")
        if self.image_saved_cnt < expected_cnt:
            print(f"Missing frames: {expected_cnt - self.image_saved_cnt}")
            print("failed: ", [(key, self.failure_cnt[key]) for key in self.failure_cnt if self.failure_cnt[key] > 0])

    def set_image_path(self, output_folder, clear_folder=True, index_offset=True, frame_first=False):
        self.enabled = True
        self.output_folder = output_folder
        self.frame_first = frame_first  # image path will be outputpath/<frameid>/<cameraid>.<format>
        if clear_folder:
            self.save_image_offset = 0
            if Path(output_folder).exists():
                shutil.rmtree(output_folder)
        elif index_offset:
            last_capture_cnt = self._find_capture_index_offset(output_folder)
            if last_capture_cnt > 0:
                clear_last = (
                    input(
                        f"\nOutput path contains a capture with {last_capture_cnt}. "
                        f"Keep previous capture and add new images to it? [Y,n]"
                    ).lower()
                    == "n"
                )
                if not clear_last:
                    print("Keeping last capture")
                    self.save_image_offset = last_capture_cnt
                else:
                    print("Clearing last capture")
                    self.save_image_offset = 0
                    if Path(output_folder).exists():
                        shutil.rmtree(output_folder)
        Path(output_folder).mkdir(parents=True, exist_ok=True)

    def save_calibration_file(self, calib):
        with open(self.output_folder + "/calibration_dome.json", "w") as file:
            json.dump(calib, file, indent=2)
        print(f"calibration file saved to {self.output_folder + '/calibration_dome.json'}")

    def _get_file_name(self, frame_idx, cam_id, is_matte=False):
        if self.frame_first:
            folder = f"{self.output_folder}/frame_{str(frame_idx + self.save_image_offset).zfill(5)}"
            if is_matte:
                folder = f"{folder}/mask"
                Path(folder).mkdir(parents=True, exist_ok=True)
                filename = f"{folder}/mask_{cam_id}{self.image_name_suffix}"
            else:
                folder = f"{folder}/rgb"
                Path(folder).mkdir(parents=True, exist_ok=True)
                filename = f"{folder}/{cam_id}{self.image_name_suffix}"
        else:
            folder = f"{self.output_folder}/{cam_id}"
            Path(folder).mkdir(parents=True, exist_ok=True)

            if is_matte:
                filename = (
                    f"{folder}/frame_{str(frame_idx + self.save_image_offset).zfill(5)}{self.image_name_suffix}_mask"
                )
            else:
                filename = f"{folder}/frame_{str(frame_idx + self.save_image_offset).zfill(5)}{self.image_name_suffix}"
        return filename

    @staticmethod
    def _find_capture_index_offset(output_folder):
        if not Path(output_folder).exists():
            return 0
        camera_folders = natsorted(os.listdir(output_folder))
        if len(camera_folders) == 0:
            return 0
        first_camera_folder = camera_folders[0]
        image_names = natsorted(os.listdir(os.path.join(output_folder, first_camera_folder)))
        if len(image_names) == 0:
            return 0
        last_image = image_names[-1]
        match = re.search(r"image(\d+)", last_image)
        if match:
            frame_number = int(match.group(1))
            return frame_number + 1
        return len(image_names)

    # region save_image
    def save_image(self, memory_view, frame_idx, cam_id, image_format, is_matte, shape):
        if image_format in image_format_functions:
            image_format_functions[image_format](self, memory_view, frame_idx, cam_id, is_matte, shape)
        else:
            print(f"No image save function defined for format {image_format}")
            raise NotImplementedError(f"No image save function defined for format {image_format}")
        # calls the @save function that implements the image_format

    @save("matte_jpg")
    def _save_matte_jpg(self, memory_view, frame_idx, cam_id, is_matte, shape):  # saves binary masks as jpg image
        matte_rle = torch.from_numpy(np.frombuffer(memory_view, dtype=np.int32).copy())
        if len(shape) == 3:  # [3, 6408, 5328]
            shape = shape[1:]  # [6408, 5328]
        matte = self.decode_mask(matte_rle, shape)
        image = Image.fromarray(((matte > 0) * 255).to(torch.uint8).numpy())
        if self.enabled:
            filename = self._get_file_name(frame_idx, cam_id, is_matte) + ".jpg"
            image.save(filename)
            with self.lock:
                self.image_saved_cnt += 1
            self.mutable_print("saved", filename)
        return image

    @staticmethod
    def decode_mask(run_length_encoded, original_shape):
        leading_one = run_length_encoded[0]
        run_lengths = run_length_encoded[1:]
        run_lengths = torch.cat((run_lengths[:1], run_lengths[1:] - run_lengths[:-1]))
        values = torch.ones_like(run_lengths) * leading_one
        values[1::2] = 1 - leading_one
        mask_flat = torch.repeat_interleave(values, run_lengths)
        return mask_flat.view(original_shape)

    @save("jpg")
    def _save_jpg(self, memory_view, frame_idx, cam_id, is_matte, shape):
        try:
            if self.enabled:
                filename = self._get_file_name(frame_idx, cam_id, is_matte) + ".jpg"
                with open(filename, "wb") as f:
                    f.write(memory_view)
                with self.lock:
                    self.image_saved_cnt += 1
                self.mutable_print("saved", filename)
            else:
                image_bytes = io.BytesIO(memory_view)
                # Debug: Check content length
                image_bytes.seek(0, io.SEEK_END)
                image = Image.open(image_bytes)
                return image
        except Exception as e:
            raise Exception(f"_save_jpg {cam_id} {e}")

    @save("matte_png")
    def _save_matte_png(self, memory_view, frame_idx, cam_id, is_matte, shape):
        image_bytes = io.BytesIO(memory_view)
        image = Image.open(image_bytes)
        if self.enabled:
            filename = self._get_file_name(frame_idx, cam_id, is_matte) + ".png"
            image.save(filename)
            self.mutable_print("saved", filename)
            self.image_saved_cnt += 1
        return image

    @save("png")
    def _save_png(self, memory_view, frame_idx, cam_id, is_matte, shape):
        image_bytes = io.BytesIO(memory_view)
        image = Image.open(image_bytes)
        if self.enabled:
            filename = self._get_file_name(frame_idx, cam_id, is_matte) + ".png"
            image.save(filename)
            self.mutable_print("saved", filename)
            self.image_saved_cnt += 1
        return image

    @save("exr")
    def _save_exr(self, memory_view, frame_idx, cam_id, is_matte, shape):
        if self.enabled:
            filename = self._get_file_name(frame_idx, cam_id, is_matte) + ".exr"
            with open(filename, "wb") as fp:
                fp.write(memory_view)
            self.mutable_print("saved", filename)
            self.image_saved_cnt += 1
        # raise NotImplementedError("exr image return not implemented, sorry")

    @save("pth")
    def _save_pth(self, memory_view, frame_idx, cam_id, is_matte, shape):
        if self.enabled:
            filename = self._get_file_name(frame_idx, cam_id, is_matte)
            image = torch.frombuffer(memory_view, dtype=torch.float32)
            torchvision.utils.save_image(image.reshape(shape), filename + ".jpg")
            torch.save(image, filename + ".pth")
            self.image_saved_cnt += 1
            self.mutable_print("saved", filename, "pth + jpg")
        # raise NotImplementedError("pth image return not implemented, sorry")

    # endregion

    def mutable_print(self, *args, **kwargs):
        if not self.silent:
            builtins.print(*args, **kwargs)

    @staticmethod
    def rename_camera_first_to_frame_first(source_directory, destination_directory):
        # Define source and destination directories
        # source_directory = Path("/home/ximea/git/vci-control/Capture/dynamic/")  # Replace with your path
        # destination_directory = Path("/home/ximea/git/vci-control/Capture/dynamic_/")  # Replace with output directory path
        destination_directory.mkdir(parents=True, exist_ok=True)

        for capture_folder in source_directory.iterdir():
            camera_names = [f.name for f in list(capture_folder.iterdir()) if ".json" not in f.name]

            print(camera_names)
            for cam_name in camera_names:
                for image_path in (capture_folder / cam_name).iterdir():
                    destination_folder = (
                        destination_directory / capture_folder.name / image_path.name.split(".")[0] / "rgb"
                    )
                    destination_folder.mkdir(parents=True, exist_ok=True)
                    destination_path = destination_folder / (cam_name + image_path.image_name_suffix)
                    shutil.move(str(image_path), str(destination_path))
                    print(f"{image_path} -> {destination_path}")
