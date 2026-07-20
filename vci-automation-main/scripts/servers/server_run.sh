#!/bin/bash

# Start a new detached screen session
screen -S vci-capture -X quit
screen -dmS vci-capture

# Create windows and run commands in them
for i in {1..15}; do
    # Pad $i to two digits with leading zeros
    padded_i=$(printf "%02d" $i)

    screen -S vci-capture -X screen -t "vci-$padded_i" bash -c "
        ssh -t vci-capture-$padded_i 'cd vci-capture && \
	docker compose down && \
        docker compose up -d --no-recreate && \
        docker compose exec vci_capture_development /bin/bash -c \"scripts/run.sh || true && exec bash\"';"
done
#git submodule update --remote my-submodule

# Attach to the session
screen -r vci-capture

