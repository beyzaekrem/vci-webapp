#!/bin/bash

# creates a screen terminal session with one server per tab
# changes directory to be within the vci-capture repo.

screen -S servers -X quit
screen -dmS servers

# Create windows and run SSH commands in them
for i in {1..15}; do
    # Pad $i to two digits with leading zeros
    padded_i=$(printf "%02d" $i)

    screen -S servers -X screen -t "vci-$padded_i" bash -c "
        ssh -t vci-capture-$padded_i 'cd vci-capture; exec bash'"
done

# Attach to the session
screen -r servers
