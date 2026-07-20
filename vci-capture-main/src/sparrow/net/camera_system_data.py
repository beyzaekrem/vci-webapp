import concurrent.futures
import json
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from typing_extensions import Self

from sparrow.gibbs_wrapper import CameraParameterError
from sparrow.net.streamable_camera import StreamableCameraManager
from sparrow.net.util import build_dir


@dataclass
class CameraSystemData:
    """
    Manages and aggregates information about all cameras on this server, including their count, configuration, serial numbers, groupings, handles, and parameters.
    """

    camera_count: int = 0
    extended_manifest: dict = field(default_factory=dict)
    serial_numbers: object = None
    parameter_json: dict = None
    handle_info: dict = None
    camera_parameters: dict = None

    def __init__(self):
        self.update_camera_count()
        self.update_extended_manifest()  # we do that in update_parameter_values
        self.update_serial_numbers()
        self.update_legacy_param_json()
        self.update_handle_info()
        self.update_parameter_values()

    def update_camera_count(self):
        self.camera_count = StreamableCameraManager().num_cameras()

    def update_extended_manifest(self):
        manifest_file = os.path.join(build_dir, "manifest.json")

        # use cached manifests if they exists
        if os.path.exists(manifest_file):
            with open(manifest_file) as file:
                self.extended_manifest = json.load(file)
                # only if camera count has changed, refresh the manifest
                # todo this is not enough to check if the manifest is outdated, we should check if the serial numbers in the manifests match the current serial numbers
                if len(self.extended_manifest) == self.camera_count:
                    print(f"Loaded all camera manifests from file. Delete {manifest_file} to refresh.")
                    return

        self.extended_manifest = {}
        for i in range(self.camera_count):
            self.extended_manifest[i] = StreamableCameraManager().get_camera_by_id(i).get_parsed_manifest()

        # cache the manifests
        def write_manifest():
            with open(manifest_file, "w") as file:
                json.dump(self.extended_manifest, file, indent=4)

        threading.Thread(target=write_manifest).start()

    def update_serial_numbers(self):
        self.serial_numbers = SerialNumberInfo()

    def update_legacy_param_json(self):
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, "param.json")
        with open(file_path, encoding="utf-8") as file:
            self.parameter_json = json.load(file)

    def update_handle_info(self):
        self.handle_info = {}
        for i in range(self.camera_count):
            self.handle_info[i] = 0 if StreamableCameraManager().get_camera_by_id(i).is_open() else -1

    def update_parameter_values(self):
        # this takes 1.6s even after optimizing, see if we can speed it up further
        self.camera_parameters = {}

        def get_camera_parameters(i):
            ret = (
                i,
                CameraParameters(
                    StreamableCameraManager().get_camera_by_id(i), self.extended_manifest.get(str(i))
                ).get_values(),
            )
            return ret

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(get_camera_parameters, i) for i in range(self.camera_count)]
            for future in concurrent.futures.as_completed(futures):
                i, params = future.result()
                self.camera_parameters[i] = params

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SerialNumberInfo:
    by_index: list
    by_sn: dict
    cam_shorthands: dict

    def __init__(self):
        self.by_index = []
        self.by_sn = {}
        self.cam_shorthands = {}
        for i in range(StreamableCameraManager().num_cameras()):
            cam = StreamableCameraManager().get_camera_by_id(i)
            sn = cam.serialnumber
            self.by_index.append(sn)
            self.by_sn[sn] = i
            self.cam_shorthands[i] = cam.camera_id


@dataclass
class CameraParameters:
    def __init__(self, cam, extended_manifest):
        self.values = {}
        if extended_manifest == None:
            print("WARN: extended manifest is None")
            # todo this happens when we do not have the manifest cached in the manifest.json file yet. if we rerun the script, it works. we should fix that
            return
        for param in extended_manifest:
            if param.get("Xiapi_Par") != None and param.get("DataType") != "Command":
                self.values[param.get("Xiapi_Par")] = ParamValue(cam, param)

    def get_values(self):
        return self.values


@dataclass
class XiError:
    errorType: str
    errorMessage: str


@dataclass
class RegisterValue:
    value: str = None
    error: XiError = None


@dataclass
class ParamValue:
    value: RegisterValue = None
    minVal: RegisterValue = None
    maxVal: RegisterValue = None
    inc: RegisterValue = None

    def __init__(self, cam, param):

        data_type = param.get("DataType")
        param_name = param.get("Xiapi_Par")
        if param_name != None:
            self.value = ParamValue.get_xiapi_param(cam, data_type, param_name)
            if data_type != "String":
                self.minVal = ParamValue.get_xiapi_param(cam, data_type, param_name + ":min")
                self.maxVal = ParamValue.get_xiapi_param(cam, data_type, param_name + ":max")
                self.inc = ParamValue.get_xiapi_param(cam, data_type, param_name + ":inc")

    def get_xiapi_param(cam, dataType, paramName):
        data_types = {"Integer": "int", "Boolean": "int", "Enumeration": "int", "Float": "float", "String": "string"}
        register = RegisterValue()
        try:
            if dataType not in data_types:
                raise RuntimeError(f"Unsupported data type {dataType} for {paramName}")
            register.value = cam.try_get_parameter(paramName, data_types[dataType])
        except CameraParameterError as e:
            error_string = str(e)  # has format "<error_name> (<error_message with spaces>)"
            error_name, error_message = error_string.split(" ", 1)
            error_message = error_message.strip(" ()")
            register.error = XiError(error_name, error_message)
        except RuntimeError as e:
            # print(f"WARN: error {e}")
            register.error = XiError("RuntimeError", str(e))
        except Exception as e:
            # print(f"WARN: error {e}")
            register.error = XiError("Exception", str(e))
        return register


class CameraSystemDataSingleton:
    """
    Singleton class that manages a single instance of CameraSystemData for use across the application.

    Methods:
        getCurrentCameraSystemData() -> CameraSystemData:
            Returns the current CameraSystemData instance managed by the singleton.

        performReload(reloadOperation: Callable[[CameraSystemData], None]):
            Executes a reload operation on the CameraSystemData instance in a thread-safe manner.
            The reloadOperation should be a callable that takes a CameraSystemData instance as its argument.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> Self:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    print("Creating CameraSystemDataSingleton")
                    cls._instance._camera_system_data = CameraSystemData()
        return cls._instance

    def getCurrentCameraSystemData(self) -> CameraSystemData:
        return self._camera_system_data

    def performReload(self, reloadOperation: Callable[[CameraSystemData], None]) -> None:
        with self._lock:
            reloadOperation(self._camera_system_data)
