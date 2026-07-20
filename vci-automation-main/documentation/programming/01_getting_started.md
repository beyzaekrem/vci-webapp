### Welcome to the controller's documentation!

The controller is a python library for communication and control of the vci-capture infrastructure. 
The Capture Stage consists of mutliple capture-servers each handling up to 6 cameras. The controller library handles the simultanious connection to all servers for you.

### Getting Started

An instance of `Controller` creates and holds the connections to the servers for you, allowing you to send and recieve messages.

```python

from controller import Controller

with Controller() as c:
    print(f"connected servers: {c.servernames}")
    print(f"connected cameras: {c.all_camera_ids_flat}")

```

### Capture images

This script captures a synchroniced image with all servers and saves it in "My_Folder".

```python
from controller import Controller, trigger_box

with Controller() as c:
    c.switch_mode("single")
    c.set_image_path("My_Folder")

    c.start()
    trigger_box("single")
    c.capture_images()
    print("done")
```

The capture-servers have different operating modes. For example, they may save the images to their local ssd storage or they can send the images directly to you. Here, we want the image directly, so we set the servers to the simple `"single" mode`. We also tell the controller which output folder to save the images to. 
Then, the capture can commence! 

With `c.start` the cameras as started. They now listen for trigger signals. We send one with `trigger_box` to all cameras at the exact same time (hardware synthronized).
Upon recieving the signal, the cameras automatically capture an image and place it into their internal buffer. Lastly, we request the buffered image with `c.capture_images`. The image is pulled from the buffer, processed, encoded, send to us and the controller saves it to My_Folder.

The contextmanager (`with Controller ...`) ensures that the cameras are closed and all images are transfered and saved before the script exits. As a failsave the triggerbox recieves an "off" signal to stop triggering images.

### The Repo

To keep the repository tidy, sort your script *scipts* or *tests*.
If you are not sure where to put something yet, place it into scripts/playground.

Any config files should be placed into *config*. This is also where the server settings `system_layout.json` is. It tells us which servers exist and what their IPs are. (If you are setting up vci-capture servers and vci-automation for a new stage, you need to update the system_layout to include your server IPs.)

If your script creates output images that are meant as a debug display, place them into *visuals*

