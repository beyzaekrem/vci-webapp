# import network_wrapper as network

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared import CAMERA_MANAGER
from sparrow.net.parse_manifest import parse_manifest

"""
trigger=0: trigger off, always capture next image
trigger=3: software trigger, call set_parameter_int("trigger_software", 1) to trigger
"""
trigger = 0


class StreamableCamera:
    def __init__(self, gibbs_camera: gibbs.Camera):
        self.gibbs_camera = gibbs_camera
        self.cached_parsed_manifest = None

    def __getattr__(self, name):
        return getattr(self.gibbs_camera, name)

    def set_parameter(self, name, value):
        """
        Sets the parameter of the camera to the specified value.
        Throws an error if that fails.
        """

        data_types = {
            "Integer": "int",
            "Boolean": "int",
            "Enumeration": "int",
            "Float": "float",
            "String": "string",
        }

        for obj in self.get_parsed_manifest():
            if obj["Xiapi_Par"] == name:
                data_type = obj["DataType"]

                if data_type not in data_types:
                    print(f"ERROR: Unknown data type {data_type}")
                    return

                self.try_set_parameter(name, data_types[data_type], str(value))
                return
        # todo better errors
        print(f"ERROR: Parameter {name} not found in manifest")

    def get_parameter(self, name: str) -> int | str | float | None:
        for obj in self.get_parsed_manifest():
            if obj["Xiapi_Par"] == name:
                data_type = obj["DataType"]
                match (data_type):
                    case "Integer" | "Boolean" | "Enumeration":
                        return self.get_parameter_int(name)
                    case "Float":
                        return self.get_parameter_float(name)
                    case "String":
                        return self.get_parameter_string(name)
                    case _:
                        print(f"ERROR: Unknown data type {data_type}")
                return None
        # todo better errors
        print(f"ERROR: Parameter {name} not found in manifest")
        return None

    def get_parsed_manifest(self) -> list[dict]:
        if self.cached_parsed_manifest is None:
            try:
                manifest_xlm:str = self.get_parameter_string("device_manifest")
                parsed: list = parse_manifest(manifest_xlm)
                self.cached_parsed_manifest = parsed
            except Exception as e:
                print(f"Camera {self.gibbs_camera.camera_id} {self.gibbs_camera.manufacturer} doesnt support 'device_manifest': {e}")
                print("Using get_manifest")
                manifest: list = self.gibbs_camera.get_manifest()
                self.cached_parsed_manifest = manifest
        return self.cached_parsed_manifest

    def get_shorthand_id(self):
        return self.gibbs_camera.camera_id


class StreamableCameraManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.streamable_cameras: dict[str, StreamableCamera] = {
            camera.camera_id: StreamableCamera(camera) for camera in CAMERA_MANAGER.cameras if camera.is_open()
        }

    def get_camera_by_id(self, camera_id: int | str) -> StreamableCamera:
        """Get a Stramable camera by index or by camera_id (e.g. C0002)."""
        if isinstance(camera_id, int):
            return list(self.streamable_cameras.values())[camera_id]
        return self.streamable_cameras[camera_id]

    def num_cameras(self) -> int:
        return len(self.streamable_cameras)

    # def get_livestreams(self) -> list:
    #     return [stream for camera in self.streamable_cameras.values() for stream in camera.get_streams()]
