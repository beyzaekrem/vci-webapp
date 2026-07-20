# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100

from collections.abc import Callable
from pathlib import Path

import pytest

import sparrow.gibbs_wrapper as gibbs
from sparrow.mode_shared.persistent_record import PersistentRecord

### helpers


def get_cache_reader(save_paths_obj: PersistentRecord, recording_name: str) -> gibbs.io.CacheReader:
    """Reusable logic to resolve path and initialize a CacheReader."""
    cache_path = save_paths_obj.get_cache_location(recording_name)
    assert cache_path is not None, "cache path should never be None"
    return gibbs.io.CacheReader(str(cache_path))


## fixutres


@pytest.fixture(scope="module")
def record_save_path(data_path: Path) -> Path:
    return data_path / "media"


@pytest.fixture(scope="module")
def cache_reader_factory(with_record_save_paths: PersistentRecord) -> Callable[[str], gibbs.io.CacheReader]:
    return lambda name: get_cache_reader(with_record_save_paths, name)


## tests
@pytest.fixture(params=["recording_001", "legacy_format_bonn_tele_bench", "legacy_format_voludogs", "fps_is_null"])
def any_recording_name(request: str) -> str:
    return request.param


def test_replay_legacy_no_pixel_layout(any_recording_name: str, cache_reader_factory) -> None:
    cache_reader: gibbs.io.CacheReader = cache_reader_factory(any_recording_name)
    fc = cache_reader.frame_count
    assert fc == 3
    assert len(cache_reader.camera_ids) == 3
    image: gibbs.GibbsImage = cache_reader.load_frame(0, 0)
    assert image is not None, " image shoudlnt be None"

    print(image, "range: ", image.pixels.min(), image.pixels.max())
    assert image.pixels.max() != 0, "image data should not be all 0 - reading failed probably"
    assert image.pixel_layout != gibbs.PixelLayout.Undefined, "pixellayout should not be Undefined"
    assert image.camera_id != "undefined", "camera_id should not be undefined"


def test_invalid_paths(cache_reader_factory) -> None:
    cache_reader: gibbs.io.CacheReader = cache_reader_factory("invalid_dump_paths")
    image: gibbs.GibbsImage = cache_reader.load_frame(0, 0)
    print(image, "range: ", image.pixels.min(), image.pixels.max())
    assert image.pixels.max() == 0, "when the dump paths are invalid, the image will be blank"
