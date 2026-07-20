# ruff: noqa: S101, N806, PLR2004, T201, TC002, INP001, RUF100
import time
from threading import Thread

import pytest

from sparrow.modes.common import BatchImageRequest, ImageAndMatteRequest, ImagePackage
from sparrow.modes.replay_handler import ProcessingCache

## testing ProcessingCache class.


@pytest.fixture
def cache() -> ProcessingCache:
    cache = ProcessingCache()
    cache.cache_depth = 5

    req = BatchImageRequest(frame_idx=list(range(10)))
    cache.prepare(req, process_fn=processing_fn)
    return cache


def processing_fn(request: ImageAndMatteRequest) -> ImagePackage:
    return ImagePackage(frame_idx=request.frame_idx)


def test_cache(cache: ProcessingCache) -> None:
    # stops at cache_depth
    time.sleep(0.1)
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4]

    # when we pop, the next one gets processed.
    assert all(
        isinstance(i, ImagePackage) for i in cache._ready.values()
    ), f"cache._ready buffer should save dict[int, ImagePackages]. But contains {cache._ready}"
    r = cache.get(cache.batch_request.to_single_request(0))
    assert r is not None, "Return ImagePackge shouldnt be None here."
    assert r.frame_idx == 0
    assert cache.frame_indeces_in_cache == [1, 2, 3, 4]
    time.sleep(0.2)
    assert cache.frame_indeces_in_cache == [1, 2, 3, 4, 5]


def test_out_or_order_pop(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    r = cache.get(cache.batch_request.to_single_request(3))
    assert r is not None, "Should be returned from cache"
    assert cache.frame_indeces_in_cache == [0, 1, 2, 4]
    time.sleep(0.2)
    assert cache.frame_indeces_in_cache == [0, 1, 2, 4, 5]


def test_request_not_in_cache(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    r = cache.get(cache.batch_request.to_single_request(20))
    assert r is None, "frame 20 is not queued. cache.get should return None -> ad-hoc processing required"
    # should return from ad-hoc processing. not from cache
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4]


def test_frame_is_queued_but_cannot_be_processed(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    r = cache.get(cache.batch_request.to_single_request(5))
    assert r is None, "the buffer is full, image 5 should be porcessed ad-hoc"
    # this is a potentail dead-lock.
    # When we request an image that is about to be processed, we can usually wait for the image to be done.
    # this behavous is important when the network operation is faster than the processing.
    # We still benefit from interleaving the processing and the networking so we should wait the short time until the frame is finished.

    # However, if the buffer is full, we cannot wait for processing, since porcessing cannot start until there is space in the buffer.
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4]

    cache.get(cache.batch_request.to_single_request(0))
    # if we then make space, the frame 5 should be in the cache
    time.sleep(0.1)
    assert 5 in cache.frame_indeces_in_cache
    # this really is a missues of the PREPARE_IMAGES and GET_IMAGES setup.
    # if you call PREPRE_IMAGES you *should* draw the images in the same order via GET_IMAGES.
    # this sepficic case here is wehre the user requested a frame out or order.


def test_we_wait_for_frame(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    cache.get(cache.batch_request.to_single_request(0))
    cache.get(cache.batch_request.to_single_request(1))

    assert cache.frame_indeces_in_cache == [2, 3, 4]

    r = cache.get(
        cache.batch_request.to_single_request(5)
    )  # this may block and wait because there is space in the buffer
    assert r is not None, "processing should wait shortly and return image 5."
    time.sleep(0.2)
    assert (
        5 not in cache.frame_indeces_in_cache
    ), f" frame 5 shouldnt be in the cache, since we waited and popped it. {cache.frame_indeces_in_cache}"


def test_frame_another_dead_lock(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    cache.get(cache.batch_request.to_single_request(0))
    assert cache.frame_indeces_in_cache == [1, 2, 3, 4]

    # one frame 5 is processed we will not have space to process frame 6 as well.
    # We cannot wait for frame 6 to be processed since that would lead to a deadlock.
    r = cache.get(cache.batch_request.to_single_request(6))
    assert r is None, "waiting for image 6 would be a deadlock so we have to process it ad-hoc"


def test_request_frame_twice(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4]

    r = cache.get(cache.batch_request.to_single_request(4))
    assert r is not None, " the first time we request image 4 we should get it"
    r = cache.get(cache.batch_request.to_single_request(4))
    assert r is None, " the second time, image 4 has been popped from the buffer so we have to process it ad-hoc"


def test_concurrent_same_frame(cache: ProcessingCache) -> None:
    time.sleep(0.1)
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4]
    # two threads request frame 4 at the same time
    results = []
    t1 = Thread(target=lambda: results.append(cache.get(cache.batch_request.to_single_request(4))))
    t2 = Thread(target=lambda: results.append(cache.get(cache.batch_request.to_single_request(4))))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len([r for r in results if r is not None]) == 1, f"only one should give us the image. {results}"


def test_waiting(cache):
    time.sleep(0.1)
    cache.cache_depth = 20
    result = []

    def slow_get():
        result.append(cache.get(cache.batch_request.to_single_request(6), allow_wait=True))

    t = Thread(target=slow_get)
    t.start()
    time.sleep(0.05)
    t.join(timeout=10.0)
    assert result[0] is not None, " its ok to wait"


def test_cancel_while_waiting(cache) -> None:
    time.sleep(0.1)
    cache.cache_depth = 20
    result = []

    def slow_get():
        result.append(cache.get(cache.batch_request.to_single_request(6), allow_wait=True))

    t = Thread(target=slow_get)
    t.start()
    time.sleep(0.05)
    cache.cancel()
    t.join(timeout=1.0)
    assert not t.is_alive(), "get should unblock after cancel"
    assert result[0] is None, " if processing prepare gets cancled while we wait in get, we should get None."


def test_prepare_replaces_active_batch(cache) -> None:
    time.sleep(0.1)
    cache.cache_depth = 20
    result = []

    def slow_get():
        result.append(cache.get(cache.batch_request.to_single_request(6), allow_wait=True))

    t = Thread(target=slow_get)
    t.start()
    time.sleep(0.05)

    new_batch = BatchImageRequest(frame_idx=list(range(20, 30)))
    cache.prepare(new_batch, process_fn=processing_fn)
    t.join(timeout=1.0)
    assert not t.is_alive()
    assert result[0] is None, "old frame shouldn't be serverd from new batch"


def test_params_mismatch_full_buffer(cache) -> None:
    time.sleep(0.1)
    assert len(cache.frame_indeces_in_cache) == 5  # buffer full
    different_request = cache.batch_request.to_single_request(0)
    different_request = different_request.model_copy(update={"quality": 50})
    result = cache.get(different_request)
    assert result is None  # params mismatch, ad hoc handled by caller
    assert len(cache.frame_indeces_in_cache) == 5  # cache untouched


def test_full_drain(cache) -> None:
    # normal happy, inteneded workflow for the cache. We get told what to prepare and get (GET_IMAGES) drains in in the same order.
    time.sleep(0.1)
    for i in range(10):  # drain all frames
        result = cache.get(cache.batch_request.to_single_request(i), allow_wait=True)
        assert result is not None
    cache._worker.join(timeout=2.0)
    assert not cache._worker.is_alive()
    assert cache.frame_indeces_in_cache == []


def test_multiple_out_of_range_concurrent(cache) -> None:
    time.sleep(0.1)
    # buffer full with 0-4, request 5, 6, 7 all at once
    results = []
    threads = [
        Thread(target=lambda i=i: results.append(cache.get(cache.batch_request.to_single_request(i), allow_wait=True)))
        for i in [5, 6, 7]
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # all should return via ad hoc, cache should be untouched
    assert cache.frame_indeces_in_cache == [0, 1, 2, 3, 4], "cache untouched"
    assert all(r is None for r in results), " the out or order requested frames all need to be processed ad hoc"
