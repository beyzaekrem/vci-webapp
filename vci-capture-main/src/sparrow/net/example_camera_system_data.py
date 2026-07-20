import json
import os
from dataclasses import asdict

from net.camera_system_data import CameraSystemData
from util import build_dir

"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
"""
import gibbs_wrapper as gibbs

for i in range(gibbs.CameraManager.num_cameras()):
    print(
        f"Open camera {i}/{gibbs.CameraManager.num_cameras()} {gibbs.CameraManager.get_camera_by_id(i).serialnumber()}"
    )
    gibbs.CameraManager.get_camera_by_id(i).open()

import time

start_time = time.time()

# Create a new WebsocketStructure object
# It will contain all the information needed for the ui client
websocketStructure = CameraSystemData()

end_time = time.time()

print(f"Time taken to create WebsocketStructure: {end_time - start_time} seconds")


# Write the websocket structure to a JSON file
with open(os.path.join(build_dir, "new_ws_content.json"), "w") as file:
    file.write(json.dumps(asdict(websocketStructure), indent=4))
