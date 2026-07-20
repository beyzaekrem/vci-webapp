import math
import threading
import time
from pathlib import Path

import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .base import Writer, WriterContext
from .image_writer import DataCategory, ImageEntry


class VideoWriter:
    """
    Creates a video of a single camera view.
    """

    def __init__(self, fps: int, output_name: Path) -> None:
        self.format = "mp4"
        self.close_requested = False
        self.check_loop_done_event = threading.Event()
        self.cache_lock = threading.Lock()
        self.image_cache: list[ImageEntry] = []

        self.current_idx = 0
        self.output_name: Path = output_name
        codec = "libx264"
        bitrate = "16M"
        self.writer = imageio.get_writer(
            str(self.output_name) + f".{self.format}",
            format="FFMPEG",
            mode="I",
            fps=fps,
            codec=codec,
            bitrate=bitrate,
        )

        self.check_image_ready_thread = threading.Thread(target=self._check_loop, daemon=False)
        self.check_image_ready_thread.start()
        print(NotImplementedError("VideoWriter has bugs"))

    def submit_image(self, image_entry: ImageEntry) -> None:  # we one image entry
        if image_entry.image_save_task is not None:
            with self.cache_lock:
                self.image_cache.append(image_entry)
                # print("append to video writer cache. ", len(self.image_cache))

    def _check_loop(self) -> None:
        self.close_requested = False
        self.check_loop_done_event.clear()
        while not self.close_requested or len(self.image_cache) > 0:
            self._write_next_frame()
            time.sleep(0.05)
        print(f"preview saved ---> {self.output_name}")
        self.writer.close()
        self.check_loop_done_event.set()

    def _write_next_frame(self):
        with self.cache_lock:
            # check if there are images in the cache
            if len(self.image_cache) == 0:
                return
            # check if oldest image is ready
            if not self.image_cache[0].is_done():
                return  # image are not saved yet

            print("write next frame to video writer")
            try:
                self.writer.append_data(np.array(self.image_cache[0].get_image()))
            except Exception as e:
                print(e)
            # remove frame from our cache
            self.image_cache.pop(0)

    def close_writer(self):
        self.close_requested = True
        if len(self.image_cache) > 0:
            self.check_loop_done_event.wait()


class PreviewWriter(Writer):
    def __init__(
        self,
        writer_context: WriterContext,
    ):
        super().__init__(writer_context)
        self.format = "mp4"
        self.selected_view_ids = None
        self.prefered_camera_ids = None
        self.image_grid_size = (3, 2)
        self.writer = None
        self.close_requested = False
        self.check_loop_done_event = threading.Event()
        self.cache_lock = threading.Lock()
        self.image_cache: dict[int, dict[str:ImageEntry]] = {}
        self.image_type: list[DataCategory] = [DataCategory.image]

        self.first_idx = -1
        self.current_idx = 0
        self.view_count = 6

        self.preview_path: Path = ""

    def preview_settings(
        self,
        prefered_camera_ids: list[str],
        frame_step: int,
        capture_fps: int,
        view_cnt: int,
    ) -> None:
        # close any previous writers (this can happen when image path is changed during runtime)
        self.close_writer()
        if len(self.image_cache) > 0:
            self.check_loop_done_event.wait()

        # create new writer
        self.preview_path = Path(self.path_structure.get_preview_path() + f".{self.format}")
        self.preview_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Creating preview writer. Writing into {self.preview_path}")

        fps = 1 if capture_fps is None else capture_fps // frame_step

        fps = max(fps, 1)  # fps cannot be less than 1

        # print(f" created preview directory {self.preview_path.parent}")

        self.frame_step = frame_step
        self.prefered_camera_ids = prefered_camera_ids
        self.selected_view_ids = None
        self.first_idx = -1
        self.current_idx = 0
        self.view_count = view_cnt

        codec = "libx264"
        bitrate = "16M"
        self.writer = imageio.get_writer(
            str(self.preview_path),
            format="FFMPEG",
            mode="I",
            fps=fps,
            codec=codec,
            bitrate=bitrate,
        )

        self.check_image_ready_thread = threading.Thread(target=self._check_loop, daemon=False)
        self.check_image_ready_thread.start()

    def submit_images(self, image_entires: list[ImageEntry]):  # we get the images of all servers
        if self.writer is None:  # preview hasn't been enabled
            return
        # when a server serves us frames, we save the frames we need for preview
        if len(image_entires) == 0:
            return

        for entry in image_entires:

            if self.first_idx == -1:  # remember the first frame index we get
                self.first_idx = entry.frame_idx

            # check if we want this frame_idx
            if (entry.frame_idx - self.first_idx) % self.frame_step != 0:
                return

            # only collect images of "our" image type
            if entry.image_type not in self.image_type:
                continue

            if self.selected_view_ids is not None:
                if entry.cam_id not in self.selected_view_ids:
                    continue

            if entry.image_save_task is not None:
                with self.cache_lock:
                    if entry.frame_idx not in self.image_cache:
                        self.image_cache[entry.frame_idx] = {}
                    view_id = entry.cam_id

                    if entry.image_type != DataCategory.image:
                        view_id = view_id + "_" + entry.image_type.name
                    self.image_cache[entry.frame_idx][view_id] = entry

    def _check_loop(self):
        self.close_requested = False
        self.check_loop_done_event.clear()
        while not self.close_requested or len(self.image_cache) > 0:
            self._write_next_frame()
            time.sleep(0.05)
        print(f"closed preview writer. Saved to {self.preview_path}")
        self.writer.close()
        self.check_loop_done_event.set()

    def _write_next_frame(self):
        with self.cache_lock:
            # check if there are images in the cache
            if len(self.image_cache) == 0:
                return

            # check if oldest image is ready
            frame_idx = next(iter(self.image_cache))
            if not all(entry.is_done() for entry in self.image_cache[frame_idx].values()):
                return  # images are not saved yet

            # on the first frame we check which camera ids we've gotten and select which camera views to have in the preview grid
            if self.selected_view_ids is None:
                view_ids = list(self.image_cache[frame_idx].keys())
                self.selected_view_ids = self.select_views(view_ids, self.prefered_camera_ids, self.view_count)
                self.image_grid_size = self.calcualte_grid_size(self.selected_view_ids)

            # merge images into one and add to video writer
            images = []
            for view_id in self.selected_view_ids:
                if view_id in self.image_cache[frame_idx]:
                    entry: ImageEntry = self.image_cache[frame_idx][view_id]
                    images.append(entry.get_image())
                else:
                    images.append(None)

            merged = self.merge_views_to_grid(images, frame_idx, self.selected_view_ids, self.image_grid_size)
            # print(f"preview writer: add frame {frame_idx}")
            self.writer.append_data(np.array(merged))

            # remove frame from our cache and update which frame we are waiting for next
            self.image_cache.pop(frame_idx)
            self.current_idx += self.frame_step

    def close_writer(self):
        self.close_requested = True
        if len(self.image_cache) > 0:
            self.check_loop_done_event.wait()

    @staticmethod
    def calcualte_grid_size(selected_camera_ids):
        # auto create gridsize max (4,2) min (1,1)
        view_cnt = len(selected_camera_ids)
        if view_cnt == 1:
            return (1, 1)
        if view_cnt > 8:
            cols = max(math.ceil(math.sqrt(view_cnt)), 1)
            rows = math.ceil(view_cnt / cols)
            return (cols, rows)
        if view_cnt <= 3:  # view_cnt 1, 2, 3 only one row
            return (view_cnt, 1)
        # 4 - 8 two rows
        return (math.ceil(view_cnt / 2), 2)

    @staticmethod
    def select_views(active_views, prefered_cameras, cnt):
        cnt = min(cnt, len(active_views))  # we can at most return all active_cameras
        prefered_active_cameras = [  # this sorts the active_cameras the same as the prefered_cameras
            cam_id for cam_id in prefered_cameras if cam_id in active_views
        ]

        if cnt < len(prefered_active_cameras):  # we don't want all the cameras from prefered list
            # evenly sample from prefered list
            selected_cameras = [
                prefered_active_cameras[int(i * len(prefered_active_cameras) / cnt)] for i in range(cnt)
            ]
            return selected_cameras
        # we want all prefered_active_cameras. Add non_prefered if we have to to reach cnt
        selected_cameras = prefered_active_cameras
        if len(selected_cameras) < cnt:
            non_prefered_cameras = [c for c in active_views if c not in selected_cameras]
            selected_cameras.extend(non_prefered_cameras[: cnt - len(selected_cameras)])
        return selected_cameras

    @staticmethod
    def merge_views_to_grid(
        images: list[Image.Image],
        image_name: int | str,
        camera_ids: list[str],
        gridsize: tuple[int, int] = (3, 2),
    ) -> Image.Image:
        """Merge PIL.Images objects into a grid."""

        grid_width = gridsize[0]
        grid_height = gridsize[1]

        image = images[0]
        w, h = image.size
        longer_side = max(w, h)
        scale_factor = longer_side // 666
        scale_factor = max(scale_factor, 1)
        w, h = (
            w // scale_factor,
            h // scale_factor,
        )  # size of each image in the grid

        final_w = w * grid_width
        final_h = h * grid_height
        # Round up to nearest multiple of 16
        final_w = ((final_w + 15) // 16) * 16
        final_h = ((final_h + 15) // 16) * 16

        grid = Image.new("RGB", (final_w, final_h))
        for idx, image in enumerate(images):
            if image is not None:
                img_tiny = image.resize((w, h))

                x = idx % grid_width * w
                y = idx // grid_width * h
                grid.paste(img_tiny, (x, y))

        # Draw frame number at the top center
        draw = ImageDraw.Draw(grid)
        try:
            font = ImageFont.truetype("arial.ttf", size=80)
        except OSError:
            font = ImageFont.load_default(size=80)
        text = f"{image_name}"
        color = "black"
        if images[0] is None:
            color = "white"
        draw.text(
            (20, h - 120),
            text,
            fill=color,
            font=font,
            stroke_width=4,
            stroke_fill="gray",
        )

        padding = 20
        # draw camera ids top right on each image in the grid
        for idx, camera_id in enumerate(camera_ids):
            x = ((idx % grid_width) + 1) * w
            y = (idx // grid_width) * h

            text_w = draw.textlength(camera_id, font)
            color = "black"
            if images[idx] is None or camera_id[0] == "M":
                color = "white"
            draw.text(
                (x - text_w - padding, y + padding),
                camera_id,
                fill=color,
                font=font,
                stroke_width=4,
                stroke_fill="gray",
            )
        return grid

    @staticmethod
    def save_image_grid(
        image_entries: list[ImageEntry], file_name: str | Path, image_name: str | None = None
    ) -> tuple[Image.Image, tuple[int, int]]:
        if image_name is None:
            image_name = file_name
        img, gridsize = PreviewWriter.create_image_grid(image_entries, image_name)
        Path(file_name).parent.mkdir(parents=True, exist_ok=True)
        img.save(file_name)
        return img, gridsize

    @staticmethod
    def create_image_grid(
        image_entries: list[ImageEntry], image_name: str | None = None
    ) -> tuple[Image.Image, tuple[int, int]]:
        if image_entries is None or len(image_entries) == 0:
            return None
        images = [entry.get_image() for entry in image_entries]
        camera_ids = [entry.cam_id for entry in image_entries]
        gridsize = PreviewWriter.calcualte_grid_size(camera_ids)

        image_grid: Image.Image = PreviewWriter.merge_views_to_grid(
            images,
            image_name,
            camera_ids,
            gridsize=gridsize,
        )
        return image_grid, gridsize
