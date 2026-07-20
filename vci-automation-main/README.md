# vci-automation

This is a Python script interface for the VCI dome.
The controller library connects to the vci-capture servers.
Users can write scripts using the src/controller library or use pre-written scripts.
This repository contains scripts for the [calibration of the cameras](documentation/calibration.md) and for [image capture](#image-capture).

# Setup

create a venv (tested with python 3.10) and activate with ```source venv/bin/activate```

install dependencies:

```sh
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
git submodule update --init --recursive
pip install -e external/vci-websocket
pip install -e .
```

test your installation and your connection to the servers:

```sh
python scripts/connection_test.py
```

# API Server
While vci-automation is intended to be used in command line, select scripts can also be used via vci-webapp. To allow this, vci-automation hast to run an api-server: `python scripts/web_service/api_server.py`.

# Network Connections

This repo connects to the rest of the capture architecture via network (vci-websocket). 
The ip addresses of the other servers is read from `config/system_layout.json`.

For **fully local development** you can run your own instance of vci-capture. Start it's server with simualted cameras as per its ReadMe. Update vci-autoamtions config/system_layout.json to point to your local vci-capture server. (Simply rename the exisitng system_layout_sim.json to system_layout.json) 

# Documentation

* vci-automation
    * [Image Capture](#image-capture)
    * [Calibrating the cameras](documentation/calibration.md)
    * [Writing my own Script (Controller library)](documentation/programming/01_getting_started.md)

* vci-common
    * [The calibration file](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/calibration_file.md)
    * [Processing steps & image formats](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md)
    * [Script collection](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/README.md#scripts) (reformating calibration file, croping images etc.)

# System Check

Before you capture, ensure that all cameras and servers are running as expected.
There are two scipts that you should run to check the system:

* ```scripts/connection_test.py```
    * In the output: check that all servers were reachable as well as the count of the connected cameras.
    * Next, check if the image capture process threw any errors. A camera might be missing calibration data, or timing-out without capturing an image.
    * Lastly, have a look at the combined preview image. If a mask shows edge-detection-like outlines of structures, the camera has been moved/bumped into, since it's last background capture and it needs to be recalibrated (or removed from the capture session if you do not have time for recalibration).
* ```tests/test.py TestRecord```
    * Check if any servers fail to reach the targeted fps count - this indicates that one of their cameras is not working properly.

[See here for solution guide.](documentation/system_control.md#the-system-check-failed-what-do-i-do-now)

# Image Capture

vci-capture provides three different capture modes: single, record/replay and ring_buffer.

### Single Mode

The single mode captures a single frame and sends it directly to the recipient (that's you).
Due to how long it takes to process and transport the images over network,
you cannot capture videos with this mode and even capturing frames back to back is not possible.
You need a little patience for this one, but you will have your images right away.
You can request your frames with any [processing steps](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md) and in any [format](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md#image-formats).
This mode is used in [``scripts/capture/single.py``](scripts/capture/single.py).

### Record & Replay

The record mode allows you to capture images and videos to the capture *servers' hard drives* ([``scripts/capture/record.py``](scripts/capture/record.py)).
You can specify the maximum recording time with the argument  
`-t MAX_TIME`  
or stop the recording at any time using **Ctrl+C**.
The images are captured in 25 FPS in raw, and you can replay (aka. download) then with the replay mode ([``scripts/capture/replay.py``](scripts/capture/replay.py)).
Since the images are recorded in raw you can request any [processing steps](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md) and any [format](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md#image-formats) you like in replay.
Record & Replay allows for the most flexibility and fps. However, you do not see your images until you've replayed them.
To delete a recording from the servers' hard drives use ([``scripts/capture/delete_recordings.py``](scripts/capture/delete_recordings.py)).

### Ring Buffer Mode

This mode is designed for real-time reconstruction.
The ring buffer mode continuously captures and processes images to a buffer on the servers.
You can request any frame idx within the ring buffer. To save time, this mode does *not* allow custom [processing steps](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/processing_steps.md).
It only supports half resolution fully processed images.
You may only request jpg images and binary mattes. This mode is used in RIFTCast (and in [``scripts/capture/ring_buffer.py``](scripts/capture/ring_buffer.py)).

## Common Questions

### Do I *have* to capture a new background all the time?

Yesn't. The background image is used for foreground-background segmentation (aka. matting). An up-to-date background is 
important to eliminate possible errors in the matting.
The image capture scripts in this repo ask for a new background every time.
You can skip this at your own judgement when it's inconvenient
(like having to move props or interrupt the flow of your capture subjects).
Small inaccuracies in the matting are usually averaged out over multiple cameras.
Just make sure you **start the session with a new background** and re-take the backgrounds when convenient.
[More](documentation/calibration.md#5-capture-new-background-images-srccalibration_take_backgroud_imagespy)

### I want to change the lighting/gain

If you want to temporarily change the lighting or gain, you can avoid [re-calibrating the colors](documentation/calibration.md#3-adjust-aperture-and-color-responses-via-color-checker-board-with-srccalibration_colorpy)
by using [``scripts/settings/find_matching_exposure.py``](scripts/settings/find_matching_exposure.py) to find which exposure time will lead to the same brightness.
Make sure to capture a new background frame with your new exposure, gain and illumination ([``scripts/calibration/take_backgroud_images.py``](scripts/calibration/take_backgroud_images.py)).

## Script Overview:

In the subfolder `scripts` are all ready-to go scripts sorted by primary purpose:

- `calibration` - scripts for calibrating the cameras. (location, lense distiotion, color response, backgorund images, etc...)
- `settings` - control over which cameras get opened as well as exposure and gain.
- `capture` - different capture routines as well as means to download and modify captured recordings.
- `web_service` - api-server control

- `dataset_tools` - scripts to modify, check and extend datasets that are already downloaded.

- `playground` - random stuff
- `servers` - (bash) scripts to control the capture servers. Require elevated permissions (ssh-keys).


## License

This project uses the `multical` library for the extrinsic calibration, which is licensed under the [GNU Lesser General Public License (LGPL) version 3](https://www.gnu.org/licenses/lgpl-3.0.html).
