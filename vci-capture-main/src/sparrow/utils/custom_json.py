import json
import re


class KeepCompact:
    """A wrapper to keep some data compact (one line) in json encoder"""

    def __init__(self, data: list | dict) -> None:
        self.data = data

    def serialize(self) -> str:
        return json.dumps(self.data, separators=(",", ": "))


class CustomEncoder(json.JSONEncoder):
    MARKER = "___JSON_REPLACE___"

    def default(self, obj) -> str:
        if isinstance(obj, KeepCompact):
            return f"{self.MARKER}{obj.serialize()}{self.MARKER}"
        return super().default(obj)

    def iterencode(self, o, _one_shot=False) -> str:
        # This catches both json.dumps() AND json.dump()
        for chunk in super().iterencode(o, _one_shot):
            # If the chunk contains our marker, we clean it up
            ret = chunk
            if self.MARKER in ret:
                # Remove the quotes and the markers
                ret = re.sub(f'"{self.MARKER}(.*?){self.MARKER}"', r"\1", ret)
            yield ret
