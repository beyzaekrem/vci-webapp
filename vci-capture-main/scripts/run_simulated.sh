#!/bin/bash

while true
do
    echo "Starting Sparrow (simulated hardware)"
    python src/sparrow/server.py --sim
    echo "Sparrow crashed or terminated, restarting..."
done
