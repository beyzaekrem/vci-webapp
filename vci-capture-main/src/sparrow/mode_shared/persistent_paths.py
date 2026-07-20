from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PersistentPaths:

    def __init__(self, config_root: Path | None = None) -> None:
        if config_root is None:
            config_root = Path(__file__).parent / "../../../persistent"
        self.set_path(config_root)

    def set_path(self, config_root: Path | str) -> None:
        persistent_dir = Path(config_root)
        self.calibration_file_path: Path = persistent_dir / "config" / "calibration_dome.json"
        self.rotation_file_path: Path = persistent_dir / "config" / "camera_rotations.json"
        self.camera_ignore_file_path: Path = persistent_dir / "config" / "camera_ignore.json"
        self.background_images_path_pattern: Path = persistent_dir / "background" / "background_raw_<camera_id>.pth"

        self.live_stream_settings_path: Path = persistent_dir / "config" / "livestream_settings.json"
        self._config_root = persistent_dir

    @property
    def config_root(self) -> Path:
        return self._config_root

    @contextmanager
    def temporary_values(self) -> any:
        """Takes a snapshot of the current path values.
        You can change them how you please during the context.
        The origial values are restored at the end."""
        old_state = copy.deepcopy(self.__dict__)
        try:
            yield self
        finally:
            # restore every field
            self.__dict__.update(old_state)


PERSISTENT_PATHS = PersistentPaths()
