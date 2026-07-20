
# System Control

The script ```scripts/servers/commands.py``` contains a collection of commands that are run directly on the servers via ssh. 
These can for example control the docker containers, reboot the servers, and turn cameras and lights on and off.

The command is passed as the first argument. For most commands you can filter the server with ```-s [server_index list]```.
Some commands let you additonally pass camera ids.


## The System Check failed, what do I do now?

#### Expected server count not reached

A Server might have crashed or was not started properly yet. Try wainting ~1 minute and re-connecting.
Otherwise you can re-start the docker run scripts with a server_run.sh bash script.
You can also check if the servers are physicaly turned on and reachable with command `echo`.
If a server cannot be reached via `echo` it might be stuck in a [bootloop](#server-unreachable---stuck-in-bootloop---showing-sys-s202).   

#### Expected camera count not reached / A server failed to reach fps count

A connected camera is not running properly.
Power cycle the connected cameras in question with `scripts/servers/commands.py reboot -s <server_index>`.
Once the server is up again (command `echo`) check if all cameras are there (command `cameras`).
If a ximea camera is missing refer to [the Ximea camera guide](cameras.md#problem-the-server-has-stopped-recognizing-one-of-the-cameras-after-the-camera-got-power-cycled).
If all cameras are connected, check the fps count. If the count is still to low, the camera may require a [Firmware reset](cameras.md#firmware-reset)


#### A camera is missing calibration info

Run the appropritate [calibration step](calibration.md).

#### A mask shows edge detection like outlines of structures

The camera has been moved/bumped into since it's last background capture and needs to be recalibrated.
If you don't have time to re-calibrate, remove the camera from the capture session with `scripts/settings/set_active_cameras.py`.

Once you have a little time, you can re-calibrate just the effected camera`s intrinsics and extrinsics 
via `scripts/calibration/charuco.py --cams <id>`. (You may select up to 5 cameras). 
You can additionally flag `--extinsics-only` if you feel certain the lense has not been messed with at all.
This partial calibration relies on the geometric integrity of the surrounding cameras, triangulating 
detected image-points between them and fitting your target camera(s).

Follow the [image capture advice](calibration.md#4-calibrate-intrinsics-and-extrinsics-via-charuco-board-with-scriptscalibrationcharucopy).
You may *concentrage the detection images on just your target camera(s)*. 
The surrouding cameras will usually capture enough points to solidly triangualte. 
Remember to cover the entire target camera(s) image-plane if intrinsic calibration is enabled.

Lastly, take [new background images](calibration.md#5-capture-new-background-images-scriptscalibration_take_backgroud_imagespy).

#### Server unreachable - stuck in bootloop - showing SYS S202

An error occured during bootup.

I've seen it being caused by the XIMEA cameras. 
A full power cycle should help:
* Turn the server off completely via the power button on the device and unplug the power. (You can unplug remotely via `server_off` command).
* Power off the connected cameras (`cameras_off`), wait ~30 seconds and power the cameras back on (`cameras_on`)
* Power the server up again (`server_on`) and wait for it to boot. (The server will auto-boot on power up.)

(`server_off` and `server_on` do not communicate with the server directly but rather with the power delivery unit. 
So it should be available to you even if the server is not reachable via ssh.)

If this doesn't work. Try booting up with the cameras off (and maybe unplugged from the server).
If you are still getting the SYS S202 loop, the issue may be caused by the SSDs or some other compoment.
Unfortunatly SYS S202 is a catch-all System Error when *something* during bootup doesn't work. 