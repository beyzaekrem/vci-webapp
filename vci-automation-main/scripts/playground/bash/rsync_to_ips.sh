#!/bin/bash

# Define the file to be rsynced and the destination path on remote machines
SOURCE_FILE="Calibration/calibration_dome.json"
DESTINATION_PATH="/media/ssd0/"
# "~/vci-capture/"
USER="xxxxx"

# Iterate over the IP range
for i in {1..15}; do
    IP="10.3.10.$i"
    echo "Starting rsync to $IP..."

    # Perform the rsync operation
    rsync -avz "$SOURCE_FILE" -e "ssh -i /home/xxxx/.ssh/id_xxxxx" "$USER@$IP:$DESTINATION_PATH"
    
    # Check if the rsync succeeded
    if [ $? -eq 0 ]; then
        echo "Rsync to $IP completed successfully."
    else
        echo "Rsync to $IP failed."
    fi
done

echo "All rsync operations complete."

