#!/bin/bash

while true
do
    echo "Starting Sparrow"
    python src/sparrow/server.py "$@"
    echo "Sparrow crashed or terminated, restarting..."
done
