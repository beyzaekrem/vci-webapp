import io
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum

import interceptor
import numpy as np
import torch
from PIL import Image

from controller.components.connection_manager import Connection
from controller.logging_config import logger

from ..exceptions import ImageWriteFailure
from .base import Writer, WriterContext
from .path_structure import DataCategory

# region save decorator
image_format_functions = {}


def save(*image_formats, **options):
    def decorator(f):
        for image_format in image_formats:
            if image_format in image_format_functions:
                raise RuntimeError(
                    f"image format {image_format} is already implemented by function {image_format_functions[image_format]}"
                )
            image_format_functions[image_format] = f
        return f

    return decorator


# endregion


class FolderMode(Enum):
    """Controls how the target output folder is treated.

    **clear** (deletes all existing content before saving)

    **append** (avoid overwriting existing images via frame offset for new images)

    **save** (saves blindly; overwrites existing files with the same name)
    """

    clear = 0  # clears the entire folder before saving images
    append = 1  # appends images to the existing images, "artifically" increasing the frame index
    save = 2  # save images blindly. Overwrites existing images my the same name.


class ImageEntry:
    """
    When we save an images from an interceptor.Message with the ImageWriter, we get a list of ImageEntries in return.
    The ImageEntry is returned immediatlely while the ImageWriters Threadpool is still busy saving the image to disk.

    Depending on the file type (jpg) the image_save_future (the task that is saving the image)
    returns a PIL Image as return value directly. In this case, requesteing is_done will tell you once the
    iamge saved and ready to be used. You get the image with get_image.

    Because its faster to simply save the memory view to disk without actually loading the Image,
    some file types (e.g. avif and exr) return None via the image_save_future.
    In this case, the ImageEntry will lazy-load the image from disk via the filename when you call ImageEntry.is_done or get_image.
    This avoids loading the image when the pipeline doesn't need it. (The preview writers usally don't need *all* images.)
    """

    def __init__(
        self,
        image_save_future: Future,  # the original network/save task
        cam_id: str,
        frame_idx: int,
        data_category: DataCategory,
        filename: str | None = None,  # filename in case we need to lazy load
        servername: str | None = None,
        thread_pool: ThreadPoolExecutor | None = None,  # threapool in case we need to lazy load
    ) -> None:
        self.cam_id: str = cam_id
        self.frame_idx: str = frame_idx
        self.image_type: DataCategory = data_category
        self.filename: str | None = filename
        self.servername: str | None = servername
        self.image_save_task: Future = image_save_future  # network/save task
        self.lazy_load_task: Future | None = None  # disk_load task
        self._cached_image: Image.Image | None = None
        self.thread_pool: ThreadPoolExecutor | None = thread_pool

    def is_done(self, *, request_lazy_load: bool = True) -> bool:
        """Non-blocking check to see if Image is ready. Triggers background image lazy-load if needed."""
        if self._cached_image is not None:
            # image save task is done and we are already holding the image in
            # hand from a previous is_done or get_images call.
            return True

        if not self.image_save_task.done():
            # image save task is still running.
            return False

        # image save is done but we aren't holding the image in our hands yet.
        if self.lazy_load_task is None:
            img_result, self.filename = self.image_save_task.result()
            if img_result is not None:
                # image save task gave us a PIL Image.
                self._cached_image = img_result
                return True
            # save task didn't give us a PIL Image (avif or exr) to avoid costly loading.
            if request_lazy_load and (self.filename and self.thread_pool):
                # lazy load is requested and possible
                self.lazy_load_task = self.thread_pool.submit(self._load_from_disk)
                return False
            # the image is done and user doesn't want to load it, or we can't lazy load.
            return True

        # lazy_load_task is running.
        if self.lazy_load_task.done():
            self._cached_image = self.lazy_load_task.result()
        # return if lazy_load is done.
        return self.lazy_load_task.done()

    def get_image(self) -> Image.Image | None:
        """
        Blocking call. Returns image immediately if ready, or waits for it to load.
        Returns a PIL.Image.
        """
        # image is ready to go
        if self._cached_image is not None:
            return self._cached_image

        # wait for the image_save_task
        img_result, self.filename = self.image_save_task.result()
        if img_result is not None:
            # image save task gave us a PIL Image.
            self._cached_image = img_result
        # we have to load the image from disk
        elif self.lazy_load_task is not None:
            # load task already started (viw is_done call).
            self._cached_image = self.lazy_load_task.result()
        else:
            # otherwise we load now. (synchronously)
            self._cached_image = self._load_from_disk()
        return self._cached_image

    def _load_from_disk(self) -> Image.Image | None:
        if not self.filename:
            return None
        try:
            img = Image.open(self.filename)
            img.load()
        except Exception as e:
            print(f"Error loading {self.filename}: {e}")
            return None
        else:
            return img


class ImageWriter(Writer):

    def __init__(
        self,
        writer_context: WriterContext,
    ):
        super().__init__(writer_context)
        self.enabled = False
        self.frame_first = False

        self.thread_pool = ThreadPoolExecutor(max_workers=30)
        self.lock = threading.Lock()
        self.image_saved_cnt = 0
        self.image_cache: list[ImageEntry] = []

        self.save_image_offset = 0
        self.image_name_suffix = ""

        self._check_loop_running = threading.Event()
        self.close_requested = False
        self.check_image_done_thread = None

    def save_images_from_response(
        self, response: interceptor.MessageIn, connection: Connection | None = None
    ) -> list[ImageEntry]:
        ret_image_entries = []
        if len(response.payload) > 0:
            frame_info = response.payload[0].ToDict()
            frame_idx = frame_info["frame_idx"]
            logger.debug(
                f"Received Image. {frame_idx} {connection.servername}. payload length {len(response.payload)}. frame-info\n{frame_info}"
            )
            image_info = frame_info.get("image_info", [])
            for idx, info in enumerate(image_info, 1):
                cam_id = info.get("camera_id")
                if cam_id is None:
                    cam_id = connection.camera_ids[(idx - 1) % len(connection.camera_ids)]
                shape = info.get("shape", [])

                # image, mask, background, mean - these go into different folders by default.
                data_category = DataCategory[info.get("data_category", "image")]

                # color, mono, depth - these go into the same folders and are prefix for the filename.
                image_type = info.get("image_type", None)
                if image_type is None:
                    image_type = "color" if cam_id[0] == "C" else "mono"

                image_format = info.get("format", "jpg")
                if data_category == DataCategory.matte:
                    image_format = "matte_" + image_format
                memory_view = bytes(response.payload[idx].PyMemoryView())
                if len(memory_view) == 1:
                    logger.warning(f"Frame is empty {cam_id} {connection.servername}")
                    ret_image_entries.append((None, cam_id, frame_idx))
                    continue
                logger.debug(f"Save image {frame_idx} {cam_id} buffer:{idx} ...")

                filename = self.path_structure.get_image_path(
                    frame_idx + self.save_image_offset,
                    cam_id,
                    data_category,
                    image_type,
                )
                future = self.thread_pool.submit(
                    self.save_image,
                    memory_view,
                    image_format,
                    filename,
                    shape,
                    self.enabled,
                )
                entry = ImageEntry(
                    image_save_future=future,
                    cam_id=cam_id,
                    frame_idx=frame_idx,
                    data_category=data_category,
                    filename=filename,
                    servername=connection.servername,
                    thread_pool=self.thread_pool,
                )
                self._add_to_cache(entry)
                ret_image_entries.append(entry)
        else:
            msg = f"Image writer expected images in response but payload is empty. {response.path}, {connection.servername}, {connection.camera_ids}"
            raise ImageWriteFailure(msg)
        return ret_image_entries

    # cache to make sure we save all images

    def _ensure_check_thread_running(self) -> None:
        if not self._check_loop_running.is_set():
            self.close_requested = False
            self._check_loop_running.set()
            self.check_image_done_thread = threading.Thread(target=self._check_loop, daemon=False)
            self.check_image_done_thread.start()

    def _add_to_cache(self, image_entry: ImageEntry) -> None:
        with self.lock:
            self.image_cache.append(image_entry)
        self._ensure_check_thread_running()

    def _check_loop(self) -> None:
        while not self.close_requested or len(self.image_cache) > 0:
            self._pop_completed()
            time.sleep(0.05)
        self._check_loop_running.clear()
        logger.debug("Image writer closed.")

    def _pop_completed(self) -> None:
        with self.lock:
            self.image_cache = [entry for entry in self.image_cache if not entry.is_done(request_lazy_load=False)]

    def wait_images_transferred(self) -> None:
        logger.debug("Wait for images to be transfered ...")
        self.close_requested = True
        if self.check_image_done_thread and self.check_image_done_thread.is_alive():
            self.check_image_done_thread.join()
        logger.debug("Images transfered.")

    def print_info(self, expected_cnt: int | None = None, image_cnt: int | None = None) -> None:
        if image_cnt is None:
            image_cnt = self.image_saved_cnt
        if expected_cnt is None:
            self.ui.log(f"Images saved {image_cnt}.")
        else:
            self.ui.log(f"Images saved {image_cnt}/{expected_cnt}.")
            if image_cnt < expected_cnt:
                self.ui.log(f"Missing frames: {expected_cnt - image_cnt}")

    def set_image_path(
        self,
        output_folder: str,
        folder_mode: FolderMode = FolderMode.clear,
        *,
        save_images: bool = True,
    ) -> None:
        self.enabled = save_images
        self.path_structure.set_output_path(output_folder)

        match folder_mode:
            case FolderMode.clear:
                self.path_structure.clear_folder(output_folder)
            case FolderMode.append:
                last_capture_cnt = self.path_structure.get_max_capture_index(output_folder)
                if last_capture_cnt > 0:
                    self.ui.log(
                        f"{self.path_structure.get_output_path()} contains a capture with {last_capture_cnt} images. Appending images."
                    )
                    self.save_image_offset = last_capture_cnt

    # region save_image
    def save_image(
        self,
        memory_view: bytes,
        image_format: str,
        filename: str,
        shape: list[int],
        save_enabled: bool,
    ) -> Image.Image | None:
        if image_format in image_format_functions:
            assert filename is not None, "Filename shouldnt never be none"
            try:
                return image_format_functions[image_format](self, memory_view, filename, shape, save_enabled)
            except Exception as e:
                msg = f"Failed to save {image_format} to {filename}: {e}"
                raise RuntimeError(msg) from e
                print(Exception(f"Failed to save {image_format} to {filename}: {e}"))
        else:
            print(f"No image save function defined for format {image_format}")
            raise NotImplementedError(f"No image save function defined for format {image_format}")
        # calls the @save function that implements the image_format

    @save("jpg", "matte_jpg")
    def _save_jpg(
        self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool
    ) -> tuple[Image.Image, str]:
        filename = filename + ".jpg"
        self._write_memory_to_file(memory_view, filename, save_enabled)

        img = self._memory_to_image(memory_view)
        return img, filename

    @staticmethod
    def _memory_to_image(memory_view: bytes) -> Image.Image:
        # Decode memory into fully loaded PIL.Image. This can incur quality loss
        image_bytes = io.BytesIO(memory_view)
        img: Image.Image = Image.open(image_bytes)
        img.load()
        return img

    def _write_memory_to_file(
        self, memory_view: bytes, filename: str, save_enabled: bool
    ) -> tuple[Image.Image | None, str]:
        if save_enabled:
            self.path_structure.create_folder(filename)
            with open(filename, "wb") as fp:
                fp.write(memory_view)
            logger.debug(f"saved {filename}")
            with self.lock:
                self.image_saved_cnt += 1
            img = None
        else:
            img = self._memory_to_image(memory_view)
        # raise NotImplementedError("exr image return not implemented, sorry")
        return img, filename

    @save("png", "matte_png")
    def _save_matte_png(
        self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool
    ) -> tuple[Image.Image | None, str]:
        return self._write_memory_to_file(memory_view, filename + ".png", save_enabled)

    @save("avif", "matte_avif", "avif_ll", "matte_avif_ll")
    def _save_avif(
        self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool
    ) -> tuple[Image.Image | None, str]:
        return self._write_memory_to_file(memory_view, filename + ".avif", save_enabled)

    @save("exr", "matte_exr")
    def _save_exr(
        self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool
    ) -> tuple[Image.Image | None, str]:
        return self._write_memory_to_file(memory_view, filename + ".exr", save_enabled)

    @save("matte_binary")
    def _save_matte_binary(
        self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool
    ) -> tuple[Image.Image, str]:  # saves binary masks as jpg image
        matte_rle = torch.from_numpy(np.frombuffer(memory_view, dtype=np.int32).copy())
        if len(shape) == 3:  # [3, 6408, 5328]
            shape = shape[1:]  # [6408, 5328]
        shape = [int(s) for s in shape]
        matte = self._decode_mask(matte_rle, shape)
        image = Image.fromarray(((matte > 0) * 255).to(torch.uint8).numpy())
        filename = filename + ".jpg"
        if save_enabled:
            self.path_structure.create_folder(filename)
            image.save(filename)
            with self.lock:
                self.image_saved_cnt += 1
            logger.debug(f"saved {filename}")
        return image, filename

    @staticmethod
    def _decode_mask(run_length_encoded: torch.tensor, original_shape: list[int]) -> torch.tensor:
        leading_one = run_length_encoded[0]
        run_lengths = run_length_encoded[1:]
        run_lengths = torch.cat((run_lengths[:1], run_lengths[1:] - run_lengths[:-1]))
        values = torch.ones_like(run_lengths) * leading_one
        values[1::2] = 1 - leading_one
        mask_flat = torch.repeat_interleave(values, run_lengths)
        return mask_flat.view(original_shape)

    @save("torch:float32")
    def _save_pth(self, memory_view: bytes, filename: str, shape: list[int], save_enabled: bool) -> tuple[None, str]:
        if save_enabled:
            self.path_structure.create_folder(filename)
            image = torch.frombuffer(memory_view, dtype=torch.float32).clone()
            # torchvision.utils.save_image(image.reshape(shape), filename + ".jpg")
            torch.save(image, filename + ".pth")
            self.image_saved_cnt += 1
            logger.debug(f"Saved {filename} pth + jpg")
        return None, filename + ".jpg"

    # endregion
