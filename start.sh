#!/bin/bash

echo "Starting Autumn Agent Background Worker..."

# Loop forever in case your script crashes
while true
do
    python3 Autumn.py
    echo "Autumn Agent crashed. Restarting in 5 seconds..."
    sleep 5
done