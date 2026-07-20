import json
from pathlib import Path

from web_app_integration.user_interface import CLIInterface, UserInterface


class SystemLayoutReader:
    def __init__(self, file_path="config/system_layout.json", user_interface: UserInterface = CLIInterface()):
        self.ui = user_interface  # todo once constructor is only called from controller (and not e.g. record.py, remove default value CLI)
        self.system_layout = None
        self.file_path = file_path
        if Path(file_path).exists():
            with open(file_path) as f:
                self.system_layout = json.load(f)
        else:
            raise Warning(f"Controller cannot find {file_path} file.")

    def check_missing(self, server_names, all_camera_ids, all_camera_ids_flat):
        if self.system_layout is None:
            return
        expected_servers = self.system_layout["servers"]

        missing_servers = [
            (server, expected_servers[server]) for server in expected_servers if server not in server_names
        ]
        if len(missing_servers) > 0:
            self.ui.log("Missing servers: ", missing_servers, "\n")
        else:
            self.ui.log("All servers connected\n")
        for servername, camera_ids in zip(server_names, all_camera_ids):
            expected_cameras = expected_servers[servername]["cameras"]
            missing_cameras = [cam for cam in expected_cameras if cam not in camera_ids]
            if len(missing_cameras) > 0:
                self.ui.log(
                    f"{servername} is missing: ",
                    missing_cameras,
                    "     ---     ",
                    [(cam_id, self.camera_position(cam_id)) for cam_id in missing_cameras],
                )
        self.ui.log()

        color_cameras = [cam_id for cam_id in all_camera_ids_flat if cam_id[0] == "C"]
        ir_cameras = [cam_id for cam_id in all_camera_ids_flat if cam_id[0] != "C"]
        self.ui.log(
            f"Connected cameras: {len(all_camera_ids_flat)}/{len(self.expected_cameras(server_names))} "
            f"({len(color_cameras)} color, {len(ir_cameras)} ir)"
            f"\n({len(server_names)}/{len(expected_servers)} servers connected)"
        )

    def camera_position(self, camera_id):
        if self.system_layout is None:
            return "no camera_list.json found"
        position_list = self.system_layout["positions"]
        for pillar in position_list:
            for plane in position_list[pillar]:
                for cam_id in position_list[pillar][plane]:
                    if camera_id == cam_id:
                        return f"{pillar}, {plane}"
        return "no position found"

    def camera_server(self, camera_id):
        if self.system_layout is None:
            return "no camera_list.json found"
        server_list = self.system_layout["servers"]
        for server_name in server_list:
            expected_cameras = server_list[server_name]["cameras"]
            if camera_id in expected_cameras:
                return server_name

    def get_center_cameras(self):
        if self.system_layout is None:
            return []
        position_list = self.system_layout["positions"]
        ret = []
        for pillar in position_list:
            for plane in position_list[pillar]:
                if plane == "center":
                    for cam_id in position_list[pillar][plane]:
                        ret.append(cam_id)
        return ret

    def expected_servers(self) -> list[str] | None:
        if self.system_layout is None:
            return None
        expected_servers = list(self.system_layout["servers"].keys())
        return [int(s.split("-")[-1]) for s in expected_servers]

    def expected_cameras(self, servers: list[str] | None = None) -> list[str] | None:
        if self.system_layout is None:
            return []

        expected_servers = servers or list(self.system_layout["servers"].keys())

        all_expected_cameras = []
        for servername in expected_servers:
            if servername not in self.system_layout["servers"]:
                msg = f"Server '{servername}' not in {self.file_path}"
                raise RuntimeError(msg)
            expected_cameras = self.system_layout["servers"][servername]["cameras"]
            all_expected_cameras.extend(expected_cameras)
        return all_expected_cameras

    def get_server_list(self) -> list[int]:
        self.check_loaded()
        return list(range(1, len(self.system_layout["servers"]) + 1))

    def get_server_address(self, server_id: int) -> str:
        """Returns (ip_adress, port) of the given vci-capture server_id. as listed in system_layout "servers" """
        self.check_loaded()
        if server_id is None:
            msg = "server_id must not be None"
            raise ValueError(msg)
        server_info = list(self.system_layout["servers"].values())[server_id - 1]
        return server_info["ip"], server_info["port"]

    def get_control_address(self) -> str:
        """Returns (ip_adress, port) of the vci-control server."""
        self.check_loaded()
        server_info = self.system_layout["control"]
        return server_info["ip"], server_info["port"]

    def get_server_name(self, server_id: int) -> str:
        self.check_loaded()
        return list(self.system_layout["servers"].keys())[server_id - 1]

    def get_expected_number_of_cameras(self) -> int:
        self.check_loaded()
        expected = self.system_layout["expected_cameras"]
        if isinstance(expected, int) and expected != 0:
            return expected
        raise Exception

    def check_loaded(self) -> None:
        if self.system_layout is None:
            msg = "System layout reader failed to load."
            raise RuntimeError(msg)
