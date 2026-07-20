#!/bin/bash

DEVICES="CUDA_VISIBLE_DEVICES=6,7"

### first: ssh to vci-gpu1 and check gpu usage
##  watch nvidia-smi -l 0.3
### select two, idle ones and write them to DEVICES

## Riftcast wants to have two GPUs for reconstruction.
## you *can* get away with one. You need to edit the vci_real.json and change the reconstruction GPU to 0
## The server will likely crash at its default 20 fps. So start the server and quickly call:
## python scripts/capture/trigger.py set_fps_10 on

## while RIFTCast is running you may call:
##      python scripts/capture/ring_buffer_peek.py
##      python scripts/settings/set_exposure_and_gain.py --force -e <exposure_profile> 



# run live RIFTCast server on vci-gpu1

# --- Configuration ---
LOCAL_USER=$(whoami)
KEY_PATH="/home/$LOCAL_USER/.ssh/vci_hector_id_ed25519 (syshub-key)"

REMOTE_HOST="administrator@vci-gpu1.cs.uni-bonn.de"
TARGET_USER="zingsheim"
TARGET_DIR="/data/home/zingsheim/Documents/Repositories/RIFTCast"
PROGRAMM="bin/RIFTCast_server /data/zingsheim/VCI_data/vci_real.json"

# --- info ---
echo "--------- task ------------"
echo "ssh $REMOTE_HOST"
echo "sudo su $TARGET_USER"
echo "cd $TARGET_DIR"
echo "$PROGRAMM"
echo "---------------------------"
echo
echo

# --- The Connection Attempt ---
echo "Attempting to connect to $REMOTE_HOST..."

# BatchMode=yes tells SSH to fail immediately if it can't login without interaction
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE_HOST" "exit" > /dev/null 2>&1; then
    echo "-------------------------------------------------------"
    echo "ERROR: Connection failed. Your SSH key might not be loaded."
    echo "Try running: ssh-add $KEY_PATH"
    echo "-------------------------------------------------------"
    exit 1
fi

echo "success"
echo
echo "changing user and running programm..."

# --- Execution ---
# -t to ensure a terminal is allocated for the sudo/su transition
ssh -tt "$REMOTE_HOST" "sudo -i -u $TARGET_USER bash -c 'cd $TARGET_DIR && $DEVICES $PROGRAMM'"

if [ $? -eq 0 ]; then
    echo "Execution successful."
else
    echo "An error occurred during remote execution."
fi