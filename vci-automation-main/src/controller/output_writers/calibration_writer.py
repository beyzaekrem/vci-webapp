import json
from datetime import datetime

from natsort import natsorted

from .base import Writer


class CalibrationWriter(Writer):

    def save_calibration_file(self, calib: dict, path: str | None = None) -> None:
        if path is None:
            path = self.path_structure.get_calibration_path()

        if path is None:
            self.ui.log("not saving calibration file")
            return
        with open(path, "w") as file:
            json.dump(calib, file, indent=2)
        self.ui.log(f"calibration file saved to {path}")


def remove_key_from_calib(calibration_data: dict, key_path: str, camera_id_filter: list[str] | None = None) -> dict:
    """
    Navigates the calibration dictionary to remove a specific key-value pair.

    The function iterates through the 'cameras' list within the calibration data. For
    each camera, it follows the nested structure defined by the key_path to locate
    and delete the target key.

    Parent dictionaries along the path that become empty as a result are pruned.

    Args:
        calibration_data (dict): The full calibration dataset, expected to contain
            a 'cameras' key with a list of camera configurations.
        key_path (str): A forward-slash-separated string representing the path to
            the key (e.g., "extrinsics/view_matrix").
        camera_id_filter (list[str] | None, optional): A list of specific 'camera_id'
            values to target. If None, the key is removed from all cameras.
            Defaults to None.

    Returns:
        dict: The modified calibration dictionary. Note that this modification
            happens in-place.
    """

    path_segments = key_path.split("/")

    # e.g.: ["path", "to", "some", "delete_key"]
    def prune(current_level: dict, path: list[str]) -> None:
        if not path or not isinstance(current_level, dict):
            # path is invalid or incomplete
            return

        target = path[0]
        # If we are at the last segment, delete the target
        if len(path) == 1:
            current_level.pop(target, None)
        else:
            # Otherwise, go deeper
            next_level = current_level.get(target)
            prune(next_level, path[1:])

            # prune empty parents
            if isinstance(next_level, dict) and not next_level:
                current_level.pop(target)

    # Apply to filtered cameras
    for cam in calibration_data.get("cameras", []):
        if camera_id_filter and cam.get("camera_id") not in camera_id_filter:
            continue
        prune(cam, path_segments)

    return calibration_data


def merge_calib_jsons(original: dict, push: dict) -> dict:
    merged = {}
    merged["meta"] = push.get("meta", "")
    merged["timestamp"] = datetime.now().strftime("%Y.%m.%d %H:%M")
    merged["cameras"] = merge_camlists(original["cameras"], push["cameras"])
    return merged


def merge_camlists(origin_camlist, push_camlist):
    # create a list[tuple(entry or None, entry or None)]
    # match entries according to their camera_id. or have their partner be none when no match is found
    # then we can just blindly merge them

    all_ids_origin = [entry["camera_id"] for entry in origin_camlist]
    all_ids_push = [entry["camera_id"] for entry in push_camlist]

    all_ids = natsorted(set(all_ids_origin + all_ids_push))

    matching_entries: list = []
    for cam_id in all_ids:
        origin_entry = None
        push_entry = None
        for entry in origin_camlist:
            if entry["camera_id"] == cam_id:
                origin_entry = entry
                break
        for entry in push_camlist:
            if entry["camera_id"] == cam_id:
                push_entry = entry
                break
        matching_entries.append((origin_entry, push_entry))  # theoretically there should never be a pair of (None,None)

    merged_list = [mergeJson(origin_entry, push_entry) for origin_entry, push_entry in matching_entries]
    return merged_list


# TODO um this is just dict update
def mergeJson(origin: dict | list | None, push: dict | list | None) -> dict:
    """
    merges two json dictionaries. Assumes that both dicts have the same data type for identical keys
    :param origin:
    :param push:
    :return:
    """
    if isinstance(origin, dict) and isinstance(push, dict):
        # push entry overwrites origin where they are different
        for key in push:  # for every key in push dictionary
            if isinstance(push[key], dict):  # next entry is a dictionary
                if key in origin:
                    origin[key] = mergeJson(origin[key], push[key])  # merge sub-dict entry of origin and push
                else:
                    origin[key] = push[key]  # origin doesn't have this dict entry
            else:  # strings, floats, integers .....
                origin[key] = push[key]  # none dictionary: replace original value with push value
                # creates value if origin doesn't have it yet.
        return origin
    if not isinstance(origin, dict) and origin is None:  # origin is not a dictionary
        return push
    if not isinstance(push, dict) and push is None:
        return origin
    return origin


if __name__ == "__main__":
    # test
    # origin_list = [{"camera_id": "C23", "extrinsics": {"view_matrix": [1, 1, 1, 1, 1, 1, 1]}},
    #                {"camera_id": "M22", "extrinsics": {"view_matrix": [2, 2, 2, 2, 2, 2, 2]}}]
    # push_list = [{"camera_id": "C23", "intrinsics": {"wb_coefficients": [23423, 1234234, 456561]}},
    #              {"camera_id": "C99", "intrinsics": {"wb_coefficients": [23423, 1234234, 456561]}}]
    # merged = merge_camlists(push_list, origin_list)
    # self.ui.log(merged, "\n")

    import json

    original = "/media/ximea/Daten/capture/bonn_tele_bench_015/calibration_dome.json"
    with open(original) as f:
        original = json.load(f)
    new_info = "/home/ximea/git/vci-automation/output/calibration_extrinsic_only.json"
    with open(new_info) as f:
        new_info = json.load(f)

    calib_json = merge_calib_jsons(original, new_info)
    with open("output/new_calibration_dome.json", "w") as f:
        json.dump(calib_json, f, indent=2)
