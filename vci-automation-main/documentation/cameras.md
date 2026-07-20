# Ximea #

## ximea tools ##

Ximea gives you two tools in its api: xiCOP and xiCamTool

xiCOP enumerates the cameras, and is command line only. ```sudo /opt/XIMEA/bin/xiCOP -offline ```

xiCamTool opens the cameras fully and gives you a gui suite sudo ```/opt/XIMEA/bin/xiCamTool```. For xiCamTool the cameras need to be closed first. So stop the capture server or shut down it's docker if vci-capture is running.

Using xiCamTool remotely via SSH requires the correct flags because it's a gui application:

- ```ssh -Y vci-capture-xx```
- ```sudo -E /opt/XIMEA/bin/xiCamTool```

## Shut down & power cycle ##

I want to shut down servers and cameras:

Turn off:
- Docker down to turn of the cameras.
- Shut down the servers. Wait until fully down.
- Then turn the camera power off.

Turn back on:
- First turn the cameras power on
- Wait for a short time.
- Then turn servers on.
- Check if all cameras are back.


Cycle a camera:

- Docker down to turn of the cameras.
- Turn the camera power off.
- Wait for a short time (~5 seconds)
- Turn the camera back on.
- Reboot the server.

## ximea camera states ##

The ximea cameras have four lights that indicate status.

camera lights:
- all off 
    - no power
- blue and red 
    - no pcie connected (no computer connected) or connection not found. When the camera is in this state the port usually glows orange to indicate that it's unavailable.
- green, red, blue blinkin and orange blinking
    - pcie connected (and enumerated) but not openend
    - The camera should be read to be openend by software either with XiCamTool or the capture pipeline.
    - If the camera id is showing up as fffff, the connection was interrupted (fiber optic cable disocnnected or camera power turned off and on. In this case you need to reboot the computer.
- green
    - camera openend and ready for capture


ports (capture card in computer):
The ports can also glow in different ways to indicate status

- orange
    - There is something connected to the port but the port is unavailabe. 
    - Fix: The computer needs to be restarted.
    - If you boot the comptuer without a pcie cable connected to a port, the port will enter this unavaliable state.

- green
    - A camera is connected to the port. The port is ready for connection/capture

- black / no light
    - the port is inactive and will not react to any cable that is connected to it.
    - Fix: connect something and restart the computer.


## Troubleshooting ##

#### Problem: The server has stopped recognizing one of the cameras after the camera got power cycled. #####
Status LEDs on the camera are showing blue and red - no connection found, the capture card LED is orange for the port in question.

Solution: First, try a full power cycle. Power down the server, then the cameras. Wait a few seconds, power the camera back up, and then the server.

If this didn't work, the camera firmware may be disrupting the pcie linking.
We need to recover the connection:
On another server, connect and open a working camera. It should be glowing green. Close the camera (it should still be green). Then Unplug the working camera's optic cable and plug into your problem camera. If the problem camera's lights are still red blue, unplug the camera's power and plug back in. The lights should switch to green, red, blue blinking, orange blinking (enumerated). In this state the problem camera is enumerated with an invalid camera-id ffffff (You could verify this with xiCOP). 
Switch the pcie cables back (leave the power cable pugged in), so the camera is connected to it's original server again.
It will stop blinking, but that's ok. The pcie linking has been overwritten by the connection with a fully initialized pcie port.
Reboot both servers, so both the problem camera and the working camera you used for the fix get properly enumerated and initialized.
The problem camera should now show up normally.
This fix is only temporary however. A full power cycle (server shutdown and camera power down) will re-create the linking issue.
The true fix, is to [reset the firmware](#firmware-reset) on the camera, which you can now do, since we've recovered pcie connection (yay).


#### Problem: A camera no longer reaches the target fps. Expecially in record capture. #####

Solution:
Power cycle the camera. Turn the camera off, wait, camera on, reboot server.

If this didn't work, [reset the camera firmware](#firmware-reset).


## Firmware reset ##

You can run a firmware update/reset with the xiCamUpdater.
Download the executable from https://www.ximea.com/support/wiki/allprod/ximea_camera_firmware_command-line_update.
Unpack and place anywhere on the server that your problem camera is connected to.
Make the xicamupdate file executable with ```chmod +x xicamupdate```.
Next determine the full serial number of your problem camera with ```sudo /opt/XIMEA/bin/xiCOP -offline```. xicamupdate needs the serialnumber to select the camera.


The xicamupdate calls and firmware version are different if you are using a different Camera Model. Please do not try to flash the incorrect firmware as that might brick the camera. In the follwoing I'm assuming Model MX245**CG**-SY-X4G3-FF or MX245**MG**-SY-X4G3-FF.

Check the current firmware on a camera with:
```sudo ./xicamupdate info FPGA2 --xiapi --camsn XJLGF225----```

Download the firmware that matches your model from https://updates.ximea.com/upd/get?action=getfile&file=fw_releases.html
It should have the model in it's name. Double check if your camera is mono or color and grab the appropriate version. I've choosen ```MX245CG-SY-X4G3-FF-F2-22_33``` for color cameras. Mono cameras should be ```MX245MG-SY-X4G3-FF-F2-22_33``` (CG vs MG).
Download and place the resulting bin (hist_20230103_040528_fw_MX245CG-SY-X4G3-FF_type_F2_ver_22_33.bin) next to the xicamupdate on the server.

Next you can execute the firmware update/reset:
```sudo ./xicamupdate prog FPGA2 hist_20230103_040528_fw_MX245CG-SY-X4G3-FF_type_F2_ver_22_33.bin --xiapi --camsn XJLGF225----```
This will take about 2 minutes. Do no interrupt the process and do not power down or unplug the camera! Don't touch anything!
Maybe don't call this from inside a docker either.

Once this is done, the camera needs to be reset for the firmware flash to take effect. The MX models are part of the xiX familiy and as such require a power cycle.