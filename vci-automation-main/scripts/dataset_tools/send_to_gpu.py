# ruff: noqa: T201, INP001
import os
import subprocess
import time

from controller import secret  # noqa: F401

# Configuration
SSH_PASSWORD = os.environ.get("GPU_PASSWORD")


def copy_to_gpu(folder, remote_server, destination):
    print(f"rsync -Pav {folder}, {remote_server}:{destination}")
    if not SSH_PASSWORD:
        print("Error: SSH_PASSWORD environment variable is not set.")
        return False

    rsync_cmd = [
        "sshpass",
        "-p",
        SSH_PASSWORD,
        "rsync",
        "-Pav",
        folder,
        f"{remote_server}:{destination}",
    ]

    try:
        subprocess.run(rsync_cmd, check=True)
        print("Sync completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"rsync failed: {e}")
        return False


def monitor_folders(watch_dir):
    while True:
        print(f"checking for folder with .copy_mefile in {watch_dir}")
        for folder in os.listdir(watch_dir):
            folder_path = os.path.join(watch_dir, folder)
            if os.path.exists(os.path.join(folder_path, ".copy_me")):
                os.remove(os.path.join(folder_path, ".copy_me"))
                success = copy_to_gpu(folder_path, "vci-gpu1", "/data/vci")
                if not success:
                    # if something fails, re-mark the folder so we know it didnt work.
                    # then exit
                    mark_folder_as_ready(folder_path)
                    raise Exception
        print("waiting...")
        time.sleep(5)


def mark_folder_as_ready(path):
    if path is None:
        return
    open(os.path.join(path, ".copy_me"), "w").close()


if __name__ == "__main__":
    # copy_to_gpu("/media/ximea/Daten/capture/bonn_tele_bench_003", "vci-gpu1", "/data/zingsheim/bonn_tele_bench/")
    monitor_folders("/media/ximea/Daten/capture/")
