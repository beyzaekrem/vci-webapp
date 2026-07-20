from __future__ import annotations

import copy
import datetime
import json
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from sparrow import gibbs_wrapper as gibbs
from sparrow.calibration_data import CalibrationData
from sparrow.calibration_data.background_images import BackgroundImages
from sparrow.utils import custom_json
from sparrow.utils.logging import logger

from .persistent import PERSISTENT_DATA


@dataclass
class RecordPaths:
    """Resolves the folder structure for recording and reading dumps from multiple ssds."""

    media_root: Path
    ssd_range: range | list

    @property
    def ssds(self) -> list[Path]:
        return [self.media_root / f"ssd{i}" for i in self.ssd_range]

    def background_image_path(self, recording_name: str) -> Path:
        return self.media_root / "ssd0" / f"{recording_name}_background_raw_<camera_id>.pth"

    def calibration_file_path(self, recording_name: str) -> Path:
        return self.media_root / "ssd0" / f"{recording_name}_calib.json"

    def cache_location(self, recording_name: str) -> Path:
        return self.media_root / "ssd0" / f"{recording_name}.cache"

    def dump_locations(self, recording_name: str) -> list[Path]:
        return [self.media_root / f"ssd{i}" / f"{recording_name}{i}" for i in self.ssd_range]

    @contextmanager
    def temporary_values(self) -> any:
        """Takes a snapshot of the current media_root and ssd_range values.
        You can change them how you please during the context.
        The origial values are restored at the end."""
        old_state = copy.deepcopy(self.__dict__)
        try:
            yield self
        finally:
            # restore every field
            self.__dict__.update(old_state)


class PersistentRecord:
    def __init__(self) -> None:
        self._recording_name = None
        self._camera_ids: list[str] = []
        self.backgrounds = BackgroundImages()
        self.calib_data = CalibrationData()
        self.paths: RecordPaths = RecordPaths(media_root=Path("/media"), ssd_range=range(8))

    def get_cache_location(self, recording_name: str | None = None) -> Path:
        if recording_name is None:
            recording_name = self._recording_name
        return self.paths.cache_location(recording_name)

    @property
    def cache_location(self) -> Path:
        return self.paths.cache_location(self._recording_name)

    @property
    def dump_locations(self) -> list[Path]:
        return self.paths.dump_locations(self._recording_name)

    def load(self, camera_ids: list[str], recording_name: str) -> None:
        self._recording_name = recording_name
        self._camera_ids = camera_ids

        logger.info(f"PERSISENT load calibration data and background for {self._recording_name} - {self._camera_ids}")

        self.calib_data.load(
            self.paths.calibration_file_path(self._recording_name), self._camera_ids, PERSISTENT_DATA.camera_rotations
        )
        assert set(self.calib_data.camera_parameters.keys()) == set(self._camera_ids)
        self.backgrounds.load(self._camera_ids, str(self.paths.background_image_path(self._recording_name)))

    def save_current_data_for_recording(self, camera_ids: list[str], recording_name: str) -> None:
        # save current background and calib from Persistent to recording persistent
        PERSISTENT_DATA.calibration_data.check_fully_calibrated(camera_ids)
        PERSISTENT_DATA.backgrounds.check_missing_backgrounds(camera_ids)

        self._recording_name = recording_name
        self._camera_ids = camera_ids
        self.backgrounds = PERSISTENT_DATA.backgrounds
        self.calib_data = PERSISTENT_DATA.calibration_data

        self.backgrounds.save(self.paths.background_image_path(self._recording_name))
        self.calib_data.save(self.paths.calibration_file_path(self._recording_name))

    def overwrite_background_images(self, new_background_images: dict[str, gibbs.GibbsImage]) -> None:
        logger.info(f"PERSISTENT RECORD overwrites background images for {self._recording_name} {self._camera_ids}")
        self.backgrounds.set_background_images(new_background_images)
        self.backgrounds.check_missing_backgrounds(self._camera_ids)
        self.backgrounds.save(self.paths.background_image_path(self._recording_name))

    def overwrite_calibration_json(self, new_calibration_json: dict) -> None:
        """
        Raises MalformedCalibrationError
        """
        self.calib_data.load(new_calibration_json, self._camera_ids, PERSISTENT_DATA.camera_rotations)
        self.calib_data.save(self.paths.calibration_file_path(self._recording_name))
        logger.info("reloading calibration and background images")
        self.load(self._camera_ids, self._recording_name)

    def rename_recording(self, old_name: str, new_name: str) -> None:
        files: list[Path] = self.get_all_file_names(old_name)
        cache_path = self.get_cache_location(old_name)
        if not cache_path.exists():
            msg = f"Recording {old_name} cannot be found"
            raise FileNotFoundError(msg)
        assert cache_path in files, "cache location must be part of the files"

        if self.get_cache_location(new_name).exists():
            msg = f"A Recording with the name {new_name} already exists. Cannot rename {old_name} to {new_name}."
            raise ValueError(msg)

        # first we find all files of the recording and decide how they *should* be renamed.
        rename_map: dict[str:str] = {}
        for file in files:
            new_file: str = str(file).replace(old_name, new_name)
            rename_map[str(file)] = new_file
        logger.info(f"renaming recording {old_name} -> {new_name}")
        logger.info("Renaming files:")
        for old, new in rename_map.items():
            logger.info(f"{old} -> {new}")

        # cache has an explicit list of its dump files. We need to update the paths there.
        # making sure we've found the dump file before and decided on a new name for them.
        with Path(cache_path).open() as f:
            cache_data = json.load(f)

        new_dump_files: list[str] = []
        for dump_path in cache_data["dump_files"]:
            if dump_path not in rename_map:
                msg = f"Renaming {old_name} to {new_name} failed. The cache {cache_path} is refering to file {dump_path} but the correspoding real file wasn't found"
                raise FileNotFoundError(msg)
            new_dump_files.append(rename_map[dump_path])
        cache_data["dump_files"] = new_dump_files

        logger.info("Executing rename...")
        self._save_cache(cache_data, cache_path)

        for old, new in rename_map.items():
            Path(old).rename(new)
        logger.info("Renaming done.")

        # sanity check
        new_files = self.get_all_file_names(new_name)
        assert set([str(s) for s in new_files]) == set(
            rename_map.values()
        ), f"searching for files of {new_name} after rename should reutrn the same files that we just renamed"

    def delete_recording(self, delete_recording: str) -> None:
        previous = self._recording_name

        self._recording_name = delete_recording

        files = self.get_all_file_names()
        logger.info(f"deleting {delete_recording}")
        for file in files:
            logger.info(f"unlink {file}")
            file.unlink()
        logger.info(f"{delete_recording} deleted.")

        self._recording_name = previous

    def get_all_file_names(self, recording_name: str | None = None) -> list[Path]:
        if recording_name is None:
            recording_name = self._recording_name
        ret = []
        # cache location
        cache_location = self.get_cache_location(recording_name)
        if cache_location.exists():
            ret.append(cache_location)
        # dump locations
        for i, ssd in enumerate(self.paths.ssds):
            dump_files = list(ssd.glob(f"{recording_name}{i}.*.dump"))  # ssd0/bla0.0.dump,
            ret.extend(dump_files)
        # calibration location
        if self.paths.calibration_file_path(recording_name).exists():
            ret.append(self.paths.calibration_file_path(recording_name))
        # background images
        pattern_path = str(self.paths.background_image_path(recording_name)).replace("<camera_id>", "*")
        ret.extend(Path(pattern_path).parent.glob(Path(pattern_path).name))
        return ret

    def delete_deprecated_backgrounds(self, delete_recording: str) -> None:
        # clear backgrounds
        image_path = self.paths.media_root / "ssd0" / f"{delete_recording}_background_<camera_id>.pth"
        pattern_path = str(image_path).replace("<camera_id>", "*")
        for file in Path(pattern_path).parent.glob(Path(pattern_path).name):
            if "raw" not in file.name:
                logger.info(f"unlink {file}")
                file.unlink()

    def get_available_recordings(self) -> list[str]:
        cache_path = list((self.paths.media_root / "ssd0").glob("*.cache"))
        return [p.stem for p in cache_path]

    def get_capture_timestamp(self, recording_name: str | None = None) -> str | None:
        if recording_name is None:
            recording_name = self._recording_name
        if recording_name is None:
            return None
        cache_path = self.get_cache_location(recording_name)
        if not cache_path.exists():
            return None

        try:
            cmd = ["stat", "-c", "%W", str(cache_path)]  # gets Birth timestamp of time via stat
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
            timestamp = int(result.stdout.strip())

            if timestamp == 0:
                return None
            dt = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo("Europe/Berlin"))
            return dt.replace(microsecond=0).isoformat()  # success

        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            return None

    def get_background_images(self, processing_steps: dict[str : list[dict]]) -> dict[str, gibbs.GibbsImage]:
        """
        Returns the background images processed with the requested steps.
        The backgrounds are cached. Requesting the same steps again, returns the background from cache.
        """
        return self.backgrounds.get_background_images(processing_steps=processing_steps, calib_data=self.calib_data)

    def update_cache(self, recording_name: str, modify_values: dict) -> None:
        """
        Opens the cache file and updates its json content with the modify_values.
        Raises:
            FileNotFoundError
        """
        cache_path: Path = self.get_cache_location(recording_name)
        with Path(cache_path).open() as f:
            cache_data: dict = json.load(f)

        # put any new items at the top (keys not preivously incuded in the cache_data)
        new_items = {key: value for key, value in modify_values.items() if key not in cache_data}
        cache_data = {**new_items, **cache_data}

        # update existing keys (without moving them)
        cache_data.update(modify_values)

        self._save_cache(cache_data, cache_path)

    def recording_exists(self, recording_name: str) -> bool:
        cache_path = self.get_cache_location(recording_name)
        return cache_path.exists()

    @staticmethod
    def _save_cache(cache_data: dict, path: Path | str) -> None:
        """Saves cache_data as json file, without expanding dump_mapping."""
        # Create a shallow copy of the dict so we don't ruin the original
        export_data = cache_data.copy()

        # Wrap the specific key for serialization
        if "dump_mapping" in export_data:
            export_data["dump_mapping"] = [
                custom_json.KeepCompact(cam_list) for cam_list in export_data["dump_mapping"]
            ]

        with Path(path).open("w") as f:
            json.dump(export_data, f, indent=1, cls=custom_json.CustomEncoder)


PERSISTENT_RECORD = PersistentRecord()
