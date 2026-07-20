import time

from natsort import natsorted

from ..exceptions import ServerDesyncError
from ..logging_config import logger
from .base import ControllerComponent


class StatusModule(ControllerComponent):

    def get_status(self, server_index: int | None = None, *, verbose: bool = False) -> list[dict]:
        """Get status dictionary of connected servers.

        The specific keys vary depending on the active server mode.
        However all modes share a few common keys.

        This includes the "camera_ids" key, containing which cameras are available in the current mode.
        For example the ring_buffer mode, excludes mono cameras. And the replay mode, returns whichever cameras were
        active during the capture of the selected recording.
        If you are looking for information about all current physically connected cameras and their hardware states,
        call `get_camera_info()`.

        - **server mode:** any
        - **API endpoint:** STATUS

        Args:
        verbose (bool): If True, requests extended info (save_paths of recording).
            Supported in specific modes only.
            Defaults to False.

        Returns:
            list[dict]: A list of status dicts.

            - common fields:
                "mode" (str): The current operational state (e.g., 'single', 'ring_buffer', 'record').
                "camera_ids" (list(str)): Identifiers for cameras available in current mode.
                "frame_count" (int): Total frames processed in the current mode since last start.
        """
        info_dicts = self.request_dict(path="STATUS", parameters={"verbose": verbose})
        if server_index is None:
            return info_dicts
        return info_dicts[server_index]

    def get_camera_info(self) -> list[dict]:
        """Gets information about the currently connected cameras and their hardware states from each server.

        This poll is mode independant and only refers to currently physically connected (and opened) cameras.
        The `get_status` call on the other hand, returns which cameras are available in the current mode.
        For example the ring_buffer mode, excludes mono cameras. And the replay mode, returns whichever cameras *were*
        active during the capture of the selected recording.

        - **server mode:** any
        - **API endpoint:** GET_CAMERA_INFO

        Returns:
            list[dict]: A list containing an info dict per server.
            - info dict:
                "num_cameras" (int): Amount of connected cameras.
                "camera_ids" (list(str)): List of camera_ids.
                "camera_info" (list(dict)): each connected camera has a correspnding camera_info entry
                    of the following structure:
                        "camera_id" (str): id of the camera,
                        "manufacturer" (str): manufacturer,
                        "running" (bool): True if the camera is running,
                        "image_type" (str): Image type captured by this camera. ("color", "mono" or "depth")
                        "exposure" (int): current exposure time in milliseconds,
                        "gain" (int): current gain
        """
        return self.request_dict(path="GET_CAMERA_INFO")

    def get_recording_info(self) -> list[dict]:
        """Get information about the stored recordings of each server.

        - **server mode:** any
        - **API endpoint:** RECORDING_INFO

        Returns:
            list[dict] : info per server.
            - structure:
                "available_recordings" (list(str)): Names of stored recordings on this server
        """
        return self.request_dict(path="RECORDING_INFO")

    def get_available_recordings(self, server_index: int | None = None) -> list[str]:
        """Retrives the names of stored recordings from requested server_index or across all servers.

        - **server mode:** any
        - **API endpoint:** RECORDING_INFO

        Args:
            server_index (int | None, optional): Filter by one server_index.
            If None, merges the available recordings of all servers. Defaults to None.

        Returns:
            list[str]: names of stored recordings
        """
        recording_info_dicts = self.get_recording_info()
        if server_index is None:
            available_recordings = set()
            for info_dict in recording_info_dicts:
                on_server = info_dict.get("available_recordings")
                available_recordings.update(on_server)
            return natsorted(list(available_recordings))

        # user specified just one server_index
        return natsorted(recording_info_dicts[server_index].get("available_recordings"))

    def get_servers_with_recording(self, recording_name: str) -> list[int]:
        """Gets the indeces of all servers that have a recording of the given name.
        Can be used to filter_connections.

        Args:
            recording_name (str): name or recording.

        Returns:
            list[int]: server indeces.
        """
        has_recording: list[int] = []
        for server_idx in range(len(self.servernames)):
            recordings_on_server = self.get_available_recordings(server_index=server_idx)
            if recording_name in recordings_on_server:
                has_recording.append(server_idx)
        return has_recording

    def get_cameras_in_recording(self, recording_name: str) -> list[str]:
        """Get all camera_ids that participated in the given recording.

        - **server mode:** replay (recording_name already set)
        - **API endpoint:** STATUS

        Args:
            recording_name (str): name of the recording.

        Returns:
            list[str]: list of camera_ids.
        """
        statuses = self.get_status()
        recording_camera_ids = []
        for s, servername in zip(statuses, self.servernames, strict=True):
            server_rec_name = s.get("recording_name", "")
            if server_rec_name != recording_name:
                logger.warning(f"sever {servername} does not have recording {recording_name}")
                continue
            recording_camera_ids.extend(s["camera_ids"])
        return recording_camera_ids

    def check_frame_count(self, *, raise_exception: bool = True) -> int:
        """Gets the frame_count of each server and checks if they match.

        - **server mode:** any
        - **API endpoint:** STATUS

        Args:
            raise_exception (bool, optional): _description_. Defaults to True.

        Raises:
            ServerDesyncError: frame_counts do not macht.

        Returns:
            int: the common frame_count.
        """
        frame_counts = [s.get("frame_count") for s in self.get_status()]
        frame_counts = [cnt for cnt in frame_counts if cnt != -1]
        if len(set(frame_counts)) == 1:
            logger.info(f"Frame counts match. {len(frame_counts)} servers captured {list(set(frame_counts))} frames")
        else:
            error = ServerDesyncError(
                f"Frame count mismatch! {len(frame_counts)} servers captured [{min(frame_counts), max(frame_counts)}] "
            )
            if raise_exception:
                raise error
            logger.error(error)
        return frame_counts

    def wait_ring_buffer_ready(self) -> None:
        """Waits until frame_count returns a value > -1.

        - **server mode:** ring_buffer
        - **API endpoint:** STATUS
        """
        while True:
            if self.check_status_reached("frame_count", ">", -1):
                logger.info("Ring buffer is ready")
                return
            time.sleep(1)
            logger.info("Waiting for first captured frame in ring_buffer... Maybe start hardware trigger?")

    def check_status_reached(self, porp: str, operation: str, value: int) -> bool:
        status_info = self.get_status(0)
        match operation:
            case "==":
                return status_info[porp] == value
            case ">":
                return status_info[porp] > value
            case "<":
                return status_info[porp] < value
        msg = f"Operation {operation} is unsupported"
        raise NotImplementedError(msg)

    def check_missing(self) -> None:
        """Prints diagonsitc of which servers and cameras are missing.
        The expected system state is described in sytem_layout"""
        self.system_layout.check_missing(
            self.servernames,
            self.camera_ids_by_server,
            self.all_camera_ids,
        )
