from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path


def _dc_default(o) -> object | None:
    """
    JSON “default” hook: if it is a dataclass, call asdict();
    if it is a Path, cast to str; otherwise let the encoder error.
    """
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"Type {type(o).__name__!r} not serializable")


@dataclass
class SavedParameter:
    """
    Represents a saved parameter with its name, value.
    """

    name: str
    value: str

    @staticmethod
    def from_dict(data: dict) -> SavedParameter:
        return SavedParameter(name=data["name"], value=data["value"])


@dataclass
class LiveStreamSettingsForCamera:
    """
    Represents the settings for a single camera.
    """

    saved_parameters: list[SavedParameter] = field(default_factory=list)

    def get_saved_parameters(self) -> list[SavedParameter]:
        return self.saved_parameters

    def get_saved_parameter(self, name: str) -> SavedParameter | None:
        return next((p for p in self.saved_parameters if p.name == name), None)

    def set_saved_parameter(self, name: str, value: str) -> None:
        param = self.get_saved_parameter(name)
        if param:
            param.value = value
        else:
            self.saved_parameters.append(SavedParameter(name=name, value=value))

    def set_trigger_source(self, trigger_source: str) -> None:
        self.set_saved_parameter("trigger_source", trigger_source)

    @staticmethod
    def from_dict(data: dict) -> LiveStreamSettingsForCamera:
        params = [SavedParameter.from_dict(p) for p in data.get("saved_parameters", [])]
        return LiveStreamSettingsForCamera(saved_parameters=params)


@dataclass
class ZoomParameters:
    center_x: float
    center_y: float
    client_size: tuple[int, int]
    zoom_factor: float

    @staticmethod
    def from_dict(data: dict) -> ZoomParameters:
        return ZoomParameters(
            center_x=data["center_x"],
            center_y=data["center_y"],
            client_size=tuple(data["client_size"]),
            zoom_factor=data["zoom_factor"],
        )

    def to_dict(self) -> dict:
        return {
            "center_x": self.center_x,
            "center_y": self.center_y,
            "client_size": list(self.client_size),
            "zoom_factor": self.zoom_factor,
        }


class LiveStreamSettings:
    """
    Holds settings for *all* cameras and saves/loads them in one JSON file.
    Now also holds zoom parameters for each livestream id.
    """

    def __init__(self, json_path: Path | str) -> None:
        self.json_path = Path(json_path)
        self.cameras: dict[str, LiveStreamSettingsForCamera] = {}
        self.livestreams: dict[str, ZoomParameters] = {}
        self._load()

    def _load(self) -> None:
        if not self.json_path.exists():
            return
        text = self.json_path.read_text(encoding="utf-8")
        data = json.loads(text)
        self.cameras = {
            serial: LiveStreamSettingsForCamera.from_dict(cam) for serial, cam in data.get("cameras", {}).items()
        }
        self.livestreams = {
            stream_id: ZoomParameters.from_dict(zp) for stream_id, zp in data.get("livestreams", {}).items()
        }

    def save(self) -> None:
        """
        Save the current settings to the JSON file.
        """
        out = {
            "cameras": self.cameras,
            "livestreams": {sid: zp.to_dict() for sid, zp in self.livestreams.items()},
        }
        self.json_path.write_text(
            json.dumps(out, default=_dc_default, indent=2),
            encoding="utf-8",
        )

    def get_camera_settings(self, serial: str) -> LiveStreamSettingsForCamera:
        if serial not in self.cameras:
            self.cameras[serial] = LiveStreamSettingsForCamera()
        return self.cameras[serial]

    def get_zoom_parameters(self, stream_id: str) -> ZoomParameters | None:
        return self.livestreams.get(stream_id)

    def set_zoom_parameters(self, stream_id: str, zoom_params: ZoomParameters) -> None:
        self.livestreams[stream_id] = zoom_params
        self.save()
