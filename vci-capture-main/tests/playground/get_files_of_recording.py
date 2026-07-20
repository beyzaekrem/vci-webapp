# ruff: noqa: T201, SLF001
import time  # noqa: I001

## checks which cameras are connected without opening them

import sparrow.gibbs_wrapper as gibbs


from sparrow.mode_shared.camera_manager import CAMERA_MANAGER
from sparrow.mode_shared.persistent_record import PERSISTENT_RECORD

PERSISTENT_RECORD._recording_name = "bonn_tele_bench_001"


def main():
    for f in PERSISTENT_RECORD.get_all_file_names():
        print(str(f))


if __name__ == "__main__":
    main()
