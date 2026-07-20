import functools
from pathlib import Path

import torch
import torchvision
from PIL import Image

from teague.calibration import Calibration, ImportSettings


class Recording(torch.nn.Module):

    def __init__(
        self,
        data_dir: Path,
        load_color: bool = True,
        load_mono: bool = False,
        load_depth: bool = True,
        import_settings: ImportSettings = ImportSettings(),
        device: torch.types.Device = "cuda:0",
        dtype: torch.dtype = torch.float,
    ) -> None:
        super().__init__()
        self.device = torch.device(device)
        self.dtype = dtype
        self.data_dir = Path(data_dir)
        self.calibration = Calibration(
            self.data_dir / "calibration_dome.json",
            load_color,
            load_mono,
            load_depth,
            import_settings,
            device,
            dtype,
        )

    def frame_dir(self, frame_idx: int) -> Path:
        return self.data_dir / f"frame_{frame_idx:05d}"

    @functools.cached_property
    def all_frame_indices(self) -> list[int]:
        frame_dirs = sorted(self.data_dir.glob("frame_*"))
        frame_indices = [int(frame_dir.name.replace("frame_", "")) for frame_dir in frame_dirs]
        return frame_indices

    def get_image_path(self, frame_idx: int, camera_id: str) -> Path:
        frame_dir = self.frame_dir(frame_idx)
        if (frame_dir / "image").exists():
            pattern_image = f"image/*_{camera_id}.*"
        elif (frame_dir / "rgb").exists():
            pattern_image = f"rgb/{camera_id}.*"
        else:
            raise ValueError(f"No image folder. Expected subfolder 'rgb' or 'image' in {self.frame_dir}")
        image_path = sorted(frame_dir.glob(pattern_image))
        if len(image_path) == 0:
            msg = f"Missing image: {frame_dir / pattern_image}"
            raise ValueError(msg)
        image_path = image_path[0]
        return image_path

    def load_image(self, frame_idx: int, camera_id: str) -> torch.Tensor:
        image_path = self.get_image_path(frame_idx, camera_id)
        image = Image.open(image_path)
        image_tensor = torchvision.transforms.functional.pil_to_tensor(image)
        image_tensor = image_tensor.to(self.device).to(self.dtype) / 255.0
        return image_tensor

    def get_mask_path(self, frame_idx: int, camera_id: str) -> Path:
        frame_dir = self.frame_dir(frame_idx)
        pattern_mask = f"mask/mask_{camera_id}.*"
        mask_path = sorted(frame_dir.glob(pattern_mask))
        if len(mask_path) == 0:
            msg = f"Missing mask: {frame_dir / pattern_mask}"
            raise ValueError(msg)
        mask_path = mask_path[0]
        return mask_path
