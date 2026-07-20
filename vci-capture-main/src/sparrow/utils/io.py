import json
from pathlib import Path


def read_json_file(calibration_path: Path) -> dict:
    if calibration_path is not None and Path.exists(Path(calibration_path)):
        data = json.loads(Path(calibration_path).read_text())
    else:
        data = {"cameras": []}
    return data


def write_json_file(path: str, data: dict) -> None:
    with Path.open(path, "w") as f:
        json.dump(data, f, indent=2)
