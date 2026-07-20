# sudo apt install sox


import threading

import requests

from .logging_config import logger

beep_ip = "http://10.3.10.20:8090/"  # server should be running on vci-capture in the user that is logged in


def camera_beep(state="beep"):
    """Send a beep command without blocking (fire and forget).
    Valid beeps: ['beep', 'boop', 'long']
    """

    def _beep():
        try:
            response = requests.get(f"{beep_ip}{state}")
            if response.status_code != 200:
                print("Camera beep failed", response.status_code)
        except requests.exceptions.ConnectionError as e:
            logger.info("Camera beep unavailable")
            logger.debug(f"Camera beep: {e}")

    threading.Thread(target=_beep, daemon=True).start()


# #import subprocess
# def camera_beep():
#     subprocess.run(["play", "-n", "synth", "0.05", "sine", "1300", "repeat", "1"])
#     subprocess.run(["play", "-n", "synth", "0.05", "sine", "1900", "repeat", "1"])


if __name__ == "__main__":
    camera_beep()
