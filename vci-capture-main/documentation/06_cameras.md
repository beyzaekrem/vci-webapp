# cmake SDK discovery

You have to install the SDKs of all camera types you want to connect to the computer.
A cmake step run via charonload attempts to find camera SDKs.
The cmake file responsible is `src/gibbs/CMakeLists.txt`.

## XIMEA Cameras

### Setup

Install xiAPI (https://www.ximea.com/support/wiki/apis/xiapi)
It should be installed to `/opt/XIMEA`

You can check the installation and camera connection by running`/opt/XIMEA/bin/xiCOP` (checks connection in command line)
or to get a GUI with image capture capabilities `/opt/XIMEA/xin/xiCamTool`.

The vci-automation repo's documentation has more infos on how to troubleshoot ximea cameras.

## Basler Cameras

### Setup
#### UEFI settings

Disable Secure boot (otherwise Kernel lockdown prevents communication with capture card).

Set PCIe Port Bifurcation in UEFI -> Devices -> PCIe Slot configurations:
    - Set capture card slots to x8 (or x8x8)
    - SSD card slot to 4x4x4x4
    - Graphics Card x16

Check if capture cards are discovered properly with `lspci | grep Basler`

Check if all SSDs are connected with `lspci -nn | grep -i  "non-volatile"`.
Ignore the "Controller" entires, they don't count.

#### Basler SDK

Install the pylon sdk. It should be a .deb that gets installed to `/opt/pylon`.

Next download the Framegrabber SDK:
Install both the Framegrabber .tar.gz and the installer script. You can leave both in the Downloads folder next to each other. 
Make the installer exectuable `chmod +x basler-fgsdk5-5.11.5.78961-linux-amd64-installer.sh` and run it.
This will unpack the tar.gz and install to /opt/FrameGrabber

Check installation by running the pylonviewer `/opt/pylon/bin/pylonviewer`
This should find the capture cards if the PCI bifurcation is set correctly in the UEFI. 
If the cards don't find all cameras, check the cards Inteface Applet: double click the card in the devices list to show its features. Select Interface Applets and set to `Acq_QuadCXP12Area` or `Acq_QuadCXP12Line`.

