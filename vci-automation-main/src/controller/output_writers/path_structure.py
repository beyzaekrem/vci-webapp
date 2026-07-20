import re
import shutil
from enum import Enum
from pathlib import Path

from natsort import natsorted


class DataCategory(Enum):
    image = 0
    matte = 1
    background = 2
    mean = 3
    preview = 4
    calib_file = 5


# defines the structure in which output is saved
class PathStructure:
    _output_path: Path | None = None
    suffix: str = ""

    IMAGE_TYPE = DataCategory

    def __init__(self) -> None:
        self.default_path_patterns: dict[DataCategory, str] = {
            DataCategory.image: "<output_path>/frame_<frame>/image/<data_type>_<cam_id><suffix>",
            DataCategory.matte: "<output_path>/frame_<frame>/mask/mask_<cam_id><suffix>",
            DataCategory.background: "<output_path>/background/<data_type>_<cam_id><suffix>",
            DataCategory.mean: "<output_path>/mean/<data_type>_<cam_id><suffix>",
            DataCategory.preview: "<output_path>/preview/image_grid<suffix>",
            DataCategory.calib_file: "<output_path>/calibration_dome<suffix>.json",
        }
        self.path_patterns: dict[DataCategory, str] = self.default_path_patterns.copy()

    def _fill_placeholders(
        self,
        pattern: str,
        frame_idx: str = "-----",
        cam_id: str = "--cam_id--",
        data_type: str = "rgb",
    ) -> str:
        placeholders = {
            "<output_path>": str(self._output_path),
            "<frame>": f"{str(frame_idx).zfill(5)}",
            "<cam_id>": cam_id,
            "<data_type>": data_type,
            "<suffix>": self.suffix,
        }

        for placeholder, value in placeholders.items():
            pattern = pattern.replace(placeholder, value)

        return pattern

    def use_default_path_patterns(self) -> None:
        self.path_patterns = self.default_path_patterns.copy()

    def get_output_path(self) -> str:
        if self._output_path is None:
            return None
        return str(self._output_path)

    def set_output_path(self, output_path: str | Path) -> None:
        self._output_path = Path(output_path)
        self._output_path.mkdir(parents=True, exist_ok=True)

    def get_calibration_path(self) -> str:
        if self._output_path is None:
            return None
        return self._fill_placeholders(self.path_patterns[DataCategory.calib_file])

    def get_preview_path(self) -> str:
        if self._output_path is None:
            return None
        return self._fill_placeholders(self.path_patterns[DataCategory.preview])

    def get_image_path(self, frame_idx: int, cam_id: str, image_type: DataCategory, data_type: str) -> str:
        if self._output_path is None:
            return "tmp"

        full_path = self._fill_placeholders(
            self.path_patterns[image_type],
            frame_idx=frame_idx,
            cam_id=cam_id,
            data_type=data_type,
        )
        return str(full_path)

    def create_folder(self, image_path: Path | str) -> None:
        Path(image_path).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_max_capture_index(output_folder: Path | str) -> int:
        output_folder = Path(output_folder)
        if not output_folder.exists():
            return 0
        camera_folders = natsorted(list(output_folder.iterdir()))
        if len(camera_folders) == 0:
            return 0
        first_camera_folder = camera_folders[0]
        image_names = natsorted(list((output_folder / first_camera_folder).iterdir))
        if len(image_names) == 0:
            return 0
        last_image = image_names[-1]
        match = re.search(r"image(\d+)", last_image)
        if match:
            frame_number = int(match.group(1))
            return frame_number + 1
        return len(image_names)

    @staticmethod
    def clear_folder(folder_path: str | Path) -> None:
        folder_path = Path(folder_path)
        try:
            for item_path in folder_path.glob("**/*"):
                if item_path.is_file() or item_path.is_symlink():
                    item_path.unlink()  # delete file or symbolic link
                elif item_path.is_dir():
                    shutil.rmtree(item_path)  # delete directory and its contents
        except FileNotFoundError:
            pass
