import sparrow.gibbs_wrapper as gibbs


class Response:
    """Wraps a MessageIn response with some accessor functions."""

    def __init__(self, promise: gibbs.interceptor.MessagePromise) -> None:
        self._response: gibbs.interceptor.MessageIn = promise.wait()

    def get_dict(self, payload_index: int = 0) -> dict:
        return self._response.payload[payload_index].ToDict()

    def assert_dict_contains(self, should_have: list[str] | str, payload_index: int = 0) -> dict:
        d = self.get_dict(payload_index=payload_index)
        should_have = should_have if isinstance(should_have, list) else [should_have]
        assert all(key in d for key in should_have), f"dict payload should contain keys: {should_have}. has: {d.keys()}"
        return d

    def __len__(self) -> int:
        return len(self._response.payload)

    def assert_elemnt_cnt(self, expected_cnt: int) -> int:
        cnt = len(self)
        assert cnt == expected_cnt, f"response should have {expected_cnt} elements. But has {cnt}"
        return cnt

    def assert_contains_images(self, expected_img_cnt: int) -> None:
        self.assert_dict_contains("image_info")
        self.assert_elemnt_cnt(1 + expected_img_cnt)  # info + images


class Client:
    def __init__(self, port: int) -> None:
        self.client = gibbs.interceptor.Client("localhost", port)
        try:
            print(f"Client: trying to connect to port {port}")
            self.client.run(blocking=False)  # this will essentailly fail immedately if the connection isnt open yet.
            self.client.wait_for_connection(1)
        except gibbs.interceptor.NotConnectedError as e:
            print(f"Client: {e}")
            raise

    def send(self, path: str, parameters: dict | None = None) -> Response:
        assert isinstance(path, str), "the path isnt no a proper string. Please fix"
        print(f"client requesting '{path}'...")
        if parameters is None:
            message = gibbs.interceptor.MessageOut(path)
        else:
            assert isinstance(parameters, dict), "the message parameters are not a proper dict. Please fix"
            parameters = gibbs.interceptor.Payload.FromDict(parameters)
            message = gibbs.interceptor.MessageOut(path, [parameters])

        promise = self.client.async_send(message)
        return Response(promise=promise)

    def switch_mode(self, mode: str, endpoint: str = "SWITCH_MODE") -> dict:
        """SWITCH_MODE and check STATUS"""
        self.send("RELEASE_CONTROL", {"force": True})
        self.send(endpoint, {"mode": mode})
        d = self.get_status()
        assert d["mode"] == mode
        return d

    def get_status(self, endpoint: str = "STATUS") -> dict:
        r = self.send(endpoint)
        return r.get_dict()

    def assert_frame_count(self, expected_cnt: int, frame_count_key: str = "frame_count") -> int:
        print(f"assert frame count = {expected_cnt}")
        s = self.get_status()
        assert (
            s[frame_count_key] == expected_cnt
        ), f"expected frame count {expected_cnt} but it is {s[frame_count_key]} - STATUS: {s}"
        return s[frame_count_key]
