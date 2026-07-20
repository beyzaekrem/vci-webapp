import argparse
import logging
import queue
import threading
import time
from pathlib import Path

import numpy as np
import torch
import viser

from teague import setup_logging
from teague.calibration import CameraCalibration, ImportSettings, LegacyImportSettings
from teague.recording import Recording

# Module logger
logger = logging.getLogger(__name__)

CAMERA_FRAMES = {}

RECORDING = None

ALL_LABELS = []

PREVIEW_IMAGE = None
PREVIEW_CAMERA_MARKDOWN = None
FRAME_INDEX_DROPDOWN = None


def add_import_elements(server: viser.ViserServer, data_dir: Path) -> None:
    with server.gui.add_folder("Import Settings"):
        up_is_down_checkbox = server.gui.add_checkbox("Up is Down", initial_value=True)

    def reload_recording() -> None:
        global RECORDING
        import_settings = ImportSettings(up_is_down=up_is_down_checkbox.value)
        RECORDING = Recording(data_dir, import_settings=import_settings)

        for camera_calibration in RECORDING.calibration.cameras.values():
            if camera_calibration.id in CAMERA_FRAMES:
                camera_frame = CAMERA_FRAMES[camera_calibration.id]
                camera_frame.position = camera_calibration.get_position().cpu().numpy()
            else:
                camera_id = camera_calibration.id
                camera_frame = server.scene.add_frame(
                    name=f"/cameras/{camera_id}",
                    position=camera_calibration.get_position().cpu().numpy(),
                    show_axes=False,
                )
                camera_sphere = server.scene.add_icosphere(
                    name=f"/cameras/{camera_id}/sphere",
                    radius=0.05,
                    color=(255, 0, 0),
                )
                camera_ids_label = server.scene.add_label(
                    name=f"/cameras/{camera_id}/label",
                    text=camera_id,
                    position=(0, 0.1, 0),
                    depth_test=True,
                    anchor="top-center",
                )
                global ALL_LABELS
                ALL_LABELS.append(camera_ids_label)

                @camera_sphere.on_click
                def _(_, camera_id=camera_id) -> None:
                    global PREVIEW_IMAGE, PREVIEW_CAMERA_MARKDOWN, RECORDING, FRAME_INDEX_DROPDOWN
                    try:
                        image = RECORDING.load_image(int(FRAME_INDEX_DROPDOWN.value), camera_id)
                        image_np = image.permute(1, 2, 0).cpu().numpy()
                        PREVIEW_IMAGE.image = image_np
                        PREVIEW_IMAGE.visible = True
                        PREVIEW_CAMERA_MARKDOWN.content = f"Camera ID: {camera_id}"
                    except ValueError as e:
                        PREVIEW_IMAGE.visible = False
                        PREVIEW_CAMERA_MARKDOWN.content = f"Error: {e}"
                        return

                CAMERA_FRAMES[camera_calibration.id] = camera_frame

    @up_is_down_checkbox.on_update
    def _(_) -> None:
        reload_recording()

    reload_recording()


def add_preview_elements(server: viser.ViserServer) -> None:
    with server.gui.add_folder("Preview"):
        global FRAME_INDEX_DROPDOWN, PREVIEW_CAMERA_MARKDOWN, PREVIEW_IMAGE
        FRAME_INDEX_DROPDOWN = server.gui.add_dropdown(
            "Frame Index",
            options=[str(idx) for idx in RECORDING.all_frame_indices],
            initial_value=str(RECORDING.all_frame_indices[0]),
        )
        PREVIEW_CAMERA_MARKDOWN = server.gui.add_markdown("No Camera Selected")
        empty = np.full((100, 100, 3), 128, dtype=np.uint8)
        PREVIEW_IMAGE = server.gui.add_image(empty, visible=False)


class AsyncImageLoadQueue:

    def __init__(self, recording: Recording = None):
        self.recording = recording
        self._queue: "queue.Queue[tuple[LookingGlassCamera, int]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, camera: "LookingGlassCamera", frame_idx: int) -> None:
        self._queue.put((camera, frame_idx))

    def _worker(self):
        while not self._stop.is_set():
            try:
                camera, frame_idx = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if self.recording is None:
                    continue
                try:
                    image = self.recording.load_image(frame_idx, camera.camera_calibration.id)
                    max_res = max(image.shape[1:])
                    if max_res > 512:
                        image = torch.nn.functional.interpolate(
                            image[None], scale_factor=512 / max_res, mode="bilinear"
                        )[0]
                except ValueError as e:
                    logger.warning(
                        "Error loading image for camera %s at frame %s: %s",
                        camera.camera_calibration.id,
                        frame_idx,
                        e,
                    )
                    image = torch.tensor([0, 0, 1.0, 0.5]).view(4, 1, 1)  # RGBA blue for missing
                camera.update_image_plane(image)
            finally:
                self._queue.task_done()
            time.sleep(0.001)

    def shutdown(self):
        self._stop.set()
        self._thread.join(timeout=1.0)


class LookingGlassCamera:
    frustrum_size: float = 0.4

    def __init__(self, viewer: "LookingGlassViewer", camera_calibration: CameraCalibration):
        self.camera_calibration = camera_calibration
        self.viewer = viewer
        self.frame = None
        self.sphere = None
        self.label = None
        self._build()

    def _build(self):
        position = self.camera_calibration.get_position().cpu().numpy()
        self.frame = self.viewer.server.scene.add_frame(
            name=f"/cameras/{self.camera_calibration.id}",
            position=position,
            show_axes=False,
        )
        self.sphere = self.viewer.server.scene.add_icosphere(
            name=f"/cameras/{self.camera_calibration.id}/sphere",
            radius=0.05,
            color=(255, 0, 0),
        )
        self.label = self.viewer.server.scene.add_label(
            name=f"/cameras/{self.camera_calibration.id}/label",
            text=self.camera_calibration.id,
            position=(0, 0.1, 0),
            depth_test=True,
            anchor="top-center",
        )
        self.frustrum = self.viewer.server.scene.add_line_segments(
            f"camera_frustrum/{self.camera_calibration.id}",
            points=[[[0, 0, 0], [0, 0, 0]]],
            colors=[128, 128, 128],
        )
        self.image_plane = self.viewer.server.scene.add_image(
            name=f"/camera_images/{self.camera_calibration.id}",
            image=np.zeros((100, 100, 4), dtype=np.uint8) + 128,
            render_width=1,
            render_height=1,
        )
        self.update_frustrum()
        self.viewer.all_labels.append(self.label)

    def update_image_plane(self, image: torch.Tensor) -> None:
        if image is None:
            image = torch.full((4, 100, 100), 0.5)
        image = (image * 255.0).clamp(0, 255).to(torch.uint8)
        self.image_plane.image = image.permute(1, 2, 0).cpu().numpy()

    def update_frustrum(self) -> None:
        corners = (
            torch.tensor(
                [
                    [0, 0],  # Top-left
                    [self.camera_calibration.resolution[0], 0],  # Top-right
                    [self.camera_calibration.resolution[0], self.camera_calibration.resolution[1]],  # Bottom-right
                    [0, self.camera_calibration.resolution[1]],  # Bottom-left
                ]
            )
            - 0.5
        )
        corners = self.camera_calibration.get_ray_samples(corners, 1, self.frustrum_size)[0]
        pose = self.camera_calibration.get_position()

        points = [[pose, corners[0, 0]], [pose, corners[1, 0]], [pose, corners[2, 0]], [pose, corners[3, 0]]]
        # Set all
        self.frustrum.points = torch.stack(list(torch.stack(line) for line in points)).cpu().numpy()
        self.image_plane.position = corners.mean(dim=0)[0].cpu().numpy()
        self.image_plane.wxyz = self.camera_calibration.get_quaternion_camera_to_world().cpu().numpy()
        self.image_plane.render_width = torch.norm(corners[1, 0] - corners[0, 0]).item()
        self.image_plane.render_height = torch.norm(corners[1, 0] - corners[2, 0]).item()

    def update(self, camera_calibration: CameraCalibration):
        self.camera_calibration = camera_calibration
        position = self.camera_calibration.get_position().cpu().numpy()
        self.frame.position = position
        self.update_frustrum()


class LookingGlassViewer:

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.cameras: dict[str, LookingGlassCamera] = {}
        self.load_queue = AsyncImageLoadQueue()
        self.recording = None
        self.all_labels = []
        self.preview_image = None
        self.preview_camera_markdown = None
        self.frame_index_dropdown = None
        # Viser
        self.server: viser.ViserServer = None
        # GUI Elements
        self.up_is_down_checkbox: viser.GuiCheckboxHandle = None

    def run(self):
        # Initial Load
        self.recording = Recording(self.data_dir)
        self.load_queue.recording = self.recording

        # Server
        self.server = viser.ViserServer(label="Looking Glass Viewer", port=8080)
        self.server.scene.set_up_direction((0, -1, 0))
        self._add_general_elements()
        self._reload_recording()

        logger.info("Press Ctrl+C to exit")

        self.server.sleep_forever()

    def _add_general_elements(self) -> None:
        self.server.gui.add_markdown(
            """
            This viewer shows the camera positions of a Looking Glass recording.
            """
        )
        with self.server.gui.add_folder("General Settings"):
            base_frame = self.server.scene.add_frame("/base/frame", axes_length=1.0)
            base_x_label = self.server.scene.add_label(
                name="/base/label_x",
                text="Right (+X)",
                position=(1.1, 0, 0),
                depth_test=True,
            )
            base_y_label = self.server.scene.add_label(
                name="/base/label_y",
                text="Down (+Y)",
                position=(0, 1.1, 0),
                depth_test=True,
            )
            base_z_label = self.server.scene.add_label(
                name="/base/label_z",
                text="Forward (+Z)",
                position=(0, 0, 1.1),
                depth_test=True,
            )
            self.all_labels.append(base_x_label)
            self.all_labels.append(base_y_label)
            self.all_labels.append(base_z_label)
            gui_frame_visible = self.server.gui.add_checkbox("Show Coordinate Frame", initial_value=True)
            gui_font_size = self.server.gui.add_slider(
                "Label Font Size", min=0.01, max=2.0, step=0.01, initial_value=1.0
            )
            gui_frustrum_size = self.server.gui.add_slider(
                "Frustrum Size", min=0.01, max=1.0, step=0.01, initial_value=LookingGlassCamera.frustrum_size
            )

            @gui_frame_visible.on_update
            def _(_) -> None:
                base_frame.visible = gui_frame_visible.value
                base_x_label.visible = gui_frame_visible.value
                base_y_label.visible = gui_frame_visible.value
                base_z_label.visible = gui_frame_visible.value

            @gui_font_size.on_update
            def _(_) -> None:
                for label in self.all_labels:
                    label.font_screen_scale = gui_font_size.value

            @gui_frustrum_size.on_update
            def _(_) -> None:
                LookingGlassCamera.frustrum_size = gui_frustrum_size.value
                for camera in self.cameras.values():
                    camera.update_frustrum()

        with self.server.gui.add_folder("Import Settings"):
            self.c0004_is_origin_checkbox = self.server.gui.add_checkbox(
                "C0004 is Origin", initial_value=self.recording.calibration.import_settings.legacy.c0004_is_origin
            )
            self.up_is_down_checkbox = self.server.gui.add_checkbox(
                "Up is Down", initial_value=self.recording.calibration.import_settings.legacy.up_is_down
            )

            @self.c0004_is_origin_checkbox.on_update
            def _(_) -> None:
                self._reload_recording()

            @self.up_is_down_checkbox.on_update
            def _(_) -> None:
                self._reload_recording()

        with self.server.gui.add_folder("Preview"):
            self.preview_camera_markdown = self.server.gui.add_markdown("No Camera Selected")
            empty = np.full((100, 100, 3), 128, dtype=np.uint8)
            self.preview_image = self.server.gui.add_image(empty, visible=False)
            self.frame_index_dropdown = self.server.gui.add_dropdown(
                "Frame Index",
                options=(
                    [str(idx) for idx in self.recording.all_frame_indices]
                    if len(self.recording.all_frame_indices) > 0
                    else ["N/A"]
                ),
                initial_value=(
                    None if len(self.recording.all_frame_indices) == 0 else str(self.recording.all_frame_indices[0])
                ),
            )

    def _reload_recording(self) -> None:
        logger.debug(
            "Reloading recording from %s (up_is_down=%s, c0004_is_origin=%s)",
            self.data_dir,
            getattr(self, "up_is_down_checkbox", None) and self.up_is_down_checkbox.value,
            getattr(self, "c0004_is_origin_checkbox", None) and self.c0004_is_origin_checkbox.value,
        )
        legacy_settings = LegacyImportSettings(
            c0004_is_origin=self.c0004_is_origin_checkbox.value,
            up_is_down=self.up_is_down_checkbox.value,
        )
        import_settings = ImportSettings(legacy=legacy_settings)
        self.recording = Recording(self.data_dir, import_settings=import_settings)
        self.load_queue.recording = self.recording

        for camera_calibration in self.recording.calibration.cameras.values():
            if camera_calibration.id in self.cameras:
                looking_glass_camera = self.cameras[camera_calibration.id]
                looking_glass_camera.update(camera_calibration)
            else:
                looking_glass_camera = LookingGlassCamera(self, camera_calibration)
                self.load_queue.submit(looking_glass_camera, self.recording.all_frame_indices[0])
                self.cameras[camera_calibration.id] = looking_glass_camera


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path, help="Path to the recording folder")
    parser.add_argument(
        "--log-level",
        "-l",
        dest="log_level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    args = parser.parse_args()
    # Configure package logging early
    try:
        setup_logging(args.log_level)
    except Exception as e:
        # If logging setup fails, fallback to basicConfig
        logging.basicConfig(level=logging.INFO)
        logger.warning("Failed to set requested log level %s: %s", args.log_level, e)
    # class Args:
    #     data_dir = None

    # args = Args()
    # args.data_dir = Path("/media/mplack/data/capture_stage/2025/2025_07_02_yoga/2025_07_02_yoga_001")

    viewer = LookingGlassViewer(data_dir=args.data_dir)
    viewer.run()


if __name__ == "__main__":
    main()
