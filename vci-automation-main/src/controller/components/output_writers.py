import copy
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from natsort import natsorted

from controller.components.base import ControllerComponent
from controller.exceptions import ServerDesyncError
from controller.logging_config import logger
from controller.output_writers.image_writer import FolderMode
from controller.processing_steps import ProcessingSteps


class OutputWritersModule(ControllerComponent):

    def get_output_folder(self) -> str:
        return self.path_structure.get_output_path()

    def set_image_path(
        self, output_folder: Path | str, folder_mode: FolderMode = FolderMode.clear, *, save_images: bool = True
    ) -> None:
        self.path_structure.set_output_path(output_folder)
        return self.image_writer.set_image_path(output_folder, folder_mode, save_images=save_images)

    def wait_images_transferred(self) -> None:
        return self.image_writer.wait_images_transferred()

    def set_preview(
        self,
        frame_step: int = 6,
        capture_fps: int | None = None,
        prefered_camera_ids: list[str] | None = None,
        view_cnt: int = 6,  # 1 to 8,
        output_path: str | None = None,
    ) -> None:
        if output_path is not None:
            self.path_structure.set_output_path(output_path)
        if prefered_camera_ids is None:
            prefered_camera_ids = self.system_layout.get_center_cameras()

        return self.preview_writer.preview_settings(prefered_camera_ids, frame_step, capture_fps, view_cnt)

    def get_raw_calibration(
        self,
        server_idx: int | None = None,
    ) -> dict:
        """Gets an unprocessed (raw) calibration dict.

        Args:
            server_idx (int | None, optional): index of the server to request from. Defaults to None - requesting from
            all servers and checks if they are matching.

        Raises:
            ServerDesyncError: Servers have mismatching calibration files.

        Returns:
            dict: calibration dict.
        """
        message = self.create_message("GET_RAW_CALIBRATION")

        if server_idx is not None:
            response = self._connection.connections[server_idx].send_message(message)
            return self.get_dict_from_responses(response)

        # when all servers are requested, we grab all and check if they are equal.
        responses = self._connection.send_message(message)
        json_objects: list[dict[str, any]] = [response.payload[0].ToDict() for response in responses]

        # Normalize and check equality
        def get_unique_calibs(json_list: list[dict]) -> set:
            normalized = [json.dumps(obj, sort_keys=True) for obj in json_list]
            return set(normalized)

        # Check if all JSON objects are the same
        unique_calibs = get_unique_calibs(json_objects)
        if len(unique_calibs) == 1:

            timestamp, mono_cnt, color_cnt, depth_cnt = self._get_calib_info(json_objects[0])
            logger.info(
                f"Servers share the same raw calibration file. Timestamp: {timestamp} "
                f"({len(color_cnt)} color, {len(mono_cnt)} ir, {len(depth_cnt)} depth)"
            )
        else:
            msg = "Warning, servers have different raw calibration files!!!"
            logger.warning(msg)
            for entry in unique_calibs:
                servers = [
                    server
                    for server, calib in zip(self.servernames, json_objects, strict=True)
                    if json.dumps(calib, sort_keys=True) == entry
                ]
                timestamp, mono_cnt, color_cnt, depth_cnt = self._get_calib_info(
                    json_objects[self.servernames.index(servers[0])]
                )
                logger.warning(
                    f"{servers} calib - {timestamp} ({len(color_cnt)} color, {len(mono_cnt)} ir, {len(depth_cnt)} depth)"
                )
            raise ServerDesyncError(msg)

        return json_objects[0]

    def check_calibration_file_sync(self) -> None:
        self.get_calibration_file(ProcessingSteps.OVERWRITE_NO_ROTATION(ProcessingSteps.RAW))

    def get_calibration_file(
        self,
        processing_steps: dict = ProcessingSteps.PROCESSED,
        camera_ids: list[str] | None = None,
        capture_fps: int | None = None,
    ) -> dict:
        logger.debug("Get calibration file")
        responses = self.send("GET_CALIBRATION_FILE", {"steps": processing_steps, "camera_ids": camera_ids})
        calibrations: list[dict[str, any]] = [response.payload[0].ToDict() for response in responses]
        logger.debug(f"calibrations: {len(calibrations)}")
        if len(calibrations) == 0:
            msg = "Didnt get any resposes for GET_CALIBRATION_FILE :("
            raise ValueError(msg)
        calib = self.merge_calibrations(calibrations)
        calib["meta"]["capture"]["fps"] = capture_fps
        return calib

    def merge_calibrations(self, calibrations: list[dict]) -> dict:
        """
        merges given calibation files by extend the different dict sections.
        assumes that meta is a dict.
        example input:
        "meta" : {"calibration": ...,"capture": ..., "name": ..., "version": ...},
        "cameras": list [camera_parameters after processing],
        "processing_applied": list [processing steps applied]
        "raw_calibration": list[camera_paramters before processing]
        """

        # check if all returned calib files have matching calibration timestamp, version number and capture name
        metas = [calib["meta"] for calib in calibrations]
        for meta in metas:
            remove_key(meta, ["capture", "number_cameras"])

        # Normalize and check equality
        def get_unique_calibs(json_list: list[dict]) -> dict[dict : list[str]]:
            temp_list = copy.deepcopy(json_list)
            # remove timestamp of the capture and check if explicitly after.
            # the timestamp can differ by a second or so without the capture actually being de-synced.
            normalized = [json.dumps(remove_key(obj, ["capture", "timestamp"]), sort_keys=True) for obj in temp_list]
            same_dict = defaultdict(list)
            for entry, server_name in zip(normalized, self.servernames, strict=True):
                same_dict[entry].append(server_name)
            return same_dict

        uniqze: dict[dict : list[str]] = get_unique_calibs(metas)
        if len(set(uniqze)) != 1:
            calib_string = "\n\n".join([f"{servers}\n{calib}" for calib, servers in uniqze.items()])
            msg = f"Mismatching meta data in calibration files:\n\n {calib_string}"
            raise ServerDesyncError(msg)

        timestamps = [datetime.fromisoformat(m["capture"]["timestamp"]) for m in metas if "capture" in m]
        if timestamps:
            drift = max(timestamps) - min(timestamps)
            if drift.total_seconds() > 2:
                msg = f"Capture timestamp deviates to much: {drift.total_seconds}s"
                raise ServerDesyncError(msg)

        meta: dict = metas[0]
        meta_sorted = {}
        custom_order = ["version", "name", "capture", "calibration"]

        def custom_sort(item: any) -> tuple[int, any]:
            if item in custom_order:
                return (0, custom_order.index(item))  # priority group, index
            return (1, item)

        meta_sections = list(meta.keys())
        meta_sections.sort(key=custom_sort)
        meta_sorted = {key: meta[key] for key in meta_sections}

        merged_calibration: dict[str, any] = {"meta": meta_sorted}

        # assemble full calib file (each server only returns their active cameras data)
        # sections like: cameras, processing_applied, raw_calibration sections.
        # we don't assume names here so we aren't as allergic to changes. We just assume that it's all lists.
        # and we exempt "meta" from this list merge operation.
        for calib in calibrations:
            sections = list(calib.keys())
            sections.remove("meta")
            for section in sections:
                if section not in merged_calibration:
                    merged_calibration[section] = []
                merged_calibration[section].extend(calib[section])
                merged_calibration[section] = natsorted(merged_calibration[section])

        counts: dict = {}
        for camera in merged_calibration["cameras"]:
            camera_type = camera.get("camera_type", camera["camera_id"][0])
            counts[camera_type] = counts.get(camera_type, 0) + 1

        merged_calibration["meta"]["capture"]["number_cameras"] = counts

        return merged_calibration

    def grab_calibration_file(
        self,
        processing_steps: dict = ProcessingSteps.PROCESSED,
        camera_ids: list[str] | None = None,
        capture_fps: int | None = None,
    ) -> dict:
        """Gets (processed, merged) calibration file from all connected servers. Saves the calib file and returns it.
        When in replay mode, the calib file saved for the selected recording is returned.
        In other modes, the current "live" calib is returned.

        - **server mode:** any
        - **API endpoint:** GET_CALIBRATION_FILE

        Args:
            processing_steps (dict, optional): processing steps applied to calibration file.
                These should match the images your are requesting. Defaults to Processing_Steps.PROCESSED.
            camera_ids (list[str] | None, optional): An optional list of camera_ids to filter for.
                     Defaults to None - include all cameras.
            capture_fps (int | None, optional): Sets the ["meta]["capture"]["fps"] field. Defaults to None.

        Returns:
            dict: processed calibration file, merged over all connected servers.
        """
        calib = self.get_calibration_file(
            processing_steps=processing_steps, camera_ids=camera_ids, capture_fps=capture_fps
        )
        # this should always work. servers only return the newer meta version through GET_CALIBRATION endpoint

        self.calibration_writer.save_calibration_file(calib)
        return calib

    @staticmethod
    def _get_calib_info(calib: dict) -> tuple[str, int, int, int]:
        timestamp = calib.get("timestamp", "-------")
        calibrated_camera_ids = [entry.get("camera_id") for entry in calib.get("cameras", [])]
        mono_cnt = [camera_id for camera_id in calibrated_camera_ids if camera_id[0] == "M"]
        color_cnt = [camera_id for camera_id in calibrated_camera_ids if camera_id[0] == "C"]
        depth_cnt = [camera_id for camera_id in calibrated_camera_ids if camera_id[0] == "D"]

        return timestamp, mono_cnt, color_cnt, depth_cnt

    def get_camera_rotations(self, server_id: int = 0) -> dict:
        message = self.create_message("GET_CAMERA_ROTATIONS")
        logger.debug(f"Get rotation from server {self.servernames[server_id]}")
        response = self._connection.connections[server_id].send_message(message)
        return self.get_dict_from_responses(response)


def remove_key(data: dict, key: str | list[str], *, no_exists_ok: bool = True) -> dict:
    """
    removes a key from a dict
    key defined can be a simple string or a path to the key like: ["meta", "capture", "timestamp"]
    """
    if not isinstance(data, dict):
        msg = f"data should is expected to be a dict. Given datatype: {type(data)}"
        raise TypeError(msg)
    key = [key] if isinstance(key, str) else key

    currentlevel = data
    for segment in key[:-1]:
        if segment in currentlevel and isinstance(currentlevel[segment], dict):
            currentlevel = currentlevel[segment]
        else:
            if no_exists_ok:
                return None
            msg = f"dict path-step-key '{segment}' not found in dict"
            raise KeyError(msg)

    final_key = key[-1]
    if final_key in currentlevel:
        currentlevel.pop(final_key)
    elif not no_exists_ok:
        msg = f"dict delete-key '{final_key}' not found in dict with path {key}"
        raise KeyError(msg)
    return data
