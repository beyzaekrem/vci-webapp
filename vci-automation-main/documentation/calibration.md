# Calibration

Calibrating the capture stage consists of multiple steps. Except for focusing the cameras you can perform 
all steps with scripts from this repository.

The information collected during calibration is saved in a .json file. 
The current calibration file can be requested from a vci-capture server: 

```python
from controller import Controller

c = Controller()
calibration_json = c.GetCalibrationFile()

with open(output_path, "w") as f:
  json.dump(calibration_json, f, indent=2) 
```

[More about the calibration file.](https://gitlab.informatik.uni-bonn.de/vci-dev/vci-common/-/blob/main/documentation/calibration_file.md)

# Calibration steps

### 1. Focus the cameras with the [VCI Webapp ](http://10.3.10.20/).

Place a calibration target (e.g: a cylinder with black and white patters) in the center of the stage. 
Open the [VCI Webapp ](http://10.3.10.20/) and use the calibrate tab. This tab displays one camera at a time and allows you to see the 
camera's live feed once un-zoomed and once zoomed to your linking. Zoom in on the calibration target. 
Loosen the cameras focus fastening with a hex key wrench (on the silver ring). Turn the lense gently until the target 
is in focus. The silver ring should *not* turn. Only the lense with the black housing should be turning. 
If the silver ring does turn, you are unscrewing it from the camera housing. Be carefull not to drop it! 
Once the target is in focus, tighten the focus fastening to lock in place. Repeat with all cameras.

(Changing the focus effects how the lense distorts the image. Therefore, you need to perform calibration charuco 
whenever you've focused a camera.)

### 2. Set camera rotation with [`scripts/calibration/set_rotation.py`](../scripts/calibration/set_rotation.py).

In this step, you set the rotation in 90 degree increments of the cameras (rot90).
This allows you to mount the cameras in landscape mode.
The script guides you through setting the rotations of all cameras that are missing this info.

### 3. Adjust aperture and color responses via color-checker board with [`scripts/calibration/color.py`](../scripts/calibration/color.py).
This step checks the overall image brightness and calibrates the color responce. This ensures that all cameras capture the subject with the same brightness and colors. For this an x-rite 24 color-checker board is captured. The board contains patches with known colors that are used as real world reference data. During the capture phase of `calibration/color.py` stand in the middle of the stage with the color baord. Turn to each camera at center hight pause for image capture. Do not tilt the board up or down as that would change how much light hits the board, skewing the calibration results. 

The output tells you if the cameras have detected a board and which brightness was detected for the white patch. 
It's important that the white patch is never overexposed as that leads to incorrect color corrections 
(usually a pink/green tint) later on.

You can adjust the brightness for all cameras by changing the exposure (currently this means changing the
exposure value in code and restarting calibration_color). Be aware that a longer exposure time leads to more motion blur.

Alternatively you can adjust an individual camera's brightness by opening/closing its aperture:
On the lense, unfasten the black thumbscrew to loosen the aperture, gently turn to adjust. 
Usually very small adjustments are enough. Tighten the thumbscrew to lock into place and re-capture the 
color-board to check the result.
Repeat until all cameras are satisfied. When possible keep the aperture small. 
This allows the subject to stay in focus even if they move closer or further away from the cameras (aka. the depth of field is larger).

This calibration step calcualtes the `white_balance_coefficients` and the `color_correction_matrix`
for the cameras. This info is saved in the calibration.json file and send to each server.

(Changing the aperture effects how the lense distorts the image.
Therefore, you need to perform calibration charuco whenever you've adjusted a camera's brightness.)

### 4. Calibrate intrinsics and extrinsics via charuco board with [`scripts/calibration/charuco.py`](../scripts/calibration/charuco.py)

The intrinsic information descibes how a camera's lense projects the real world onto the image, while the extrinsic view matrix represents the camera pose. The calibration/charuco scripts allows you to calibrate both of these aspects by capturing a charuco board (chessboard with aruco codes). The features on the board are easy to detect in images and thereby provide real world reference data.

During the capture phase of the calibration/charuco script slowly walk through the stage with a charuco board, pause for each image capture.

First, we capture close up images of the board. This is mainly intened for the *intrinsic calibration*, which needs the *entire field of view of each camera to be covered*. 
*Hold the board up close to each camera*. Stand close to the edge of the stage to do this.
For the bottom row of cameras, rest the board on the floor. For the top row, hold the board high above your head.
The script periodically outputs a display image, showing all detected points. You can check this to see your coverage. Pay attention to the top and bottom image edges as those tend to we left out.

Next, we will capture board poses for the extrinsic calibration. In this step it is important to capture the board at different distances (and angles) from the camera. 
  - Stand in the *center of the stage and turn to each camera* (at center height). Repeat holding the board high
  - Stand in the *middle distance* between center and edge. Circle around the stage, showing the board to each camera.
  - Stand at the *edge of the stage*, with your back toward the cameras behind you, so the cameras capture the board at the largest distance. Circle around the stage. 

Check the display image and fill any obvious gaps.

Lastly, capture the origin with the corresponding input command of the script. You need to lay the board face up on the ground roughly in the center of the stage. This captures the height and orientation of the ground. The exact position doesn't matter, however the origin capture is only successfull if the camera indicated in the interactive script can detect enough board points. You can request an image of the camera to see how you need to move the board to get a successfull detection.

When you are done, stop the image capture and the calibration will run automatically.
The detected points are saved in a json file. When you re-run the script, it will ask if you want to add to your last detections. 
You can also redo the calibration using the points from the file with the `--redo` flag.

This calibration step calculates the extrinsic `view_matrix` and intrinsics: `camera_matrix`, 
`resolution` and `distortion_coefficients`.

Once the calibration is done, you can display the camera positions with `python scripts/calibration/plot.py`.
If you pass the location of the detected points, the 3D locations of the points is also plotted.

### 5. Capture new background images [`scripts/calibration/take_backgroud_image.py`](../scripts/calibration/take_backgroud_images.py)

The background matting during image capture needs an up-to-date background image for each camera. 
A new background frame is needed when the cameras have been changed (focus, aperture, positions), 
the lighting has been changed, or when objects in the background have been moved.
Capture new backgrounds before each capturing session. When possible, capture new backgrounds 
between different subjects / clips so small changes in the background don't accumulate over time 
and degrade the matting.

### changing the lenses

You can change between wide angle and narrow lenses. To change the lense: unscrew the entire lense from the camera housing.
Then perform all calibration steps with the new lenses. 
