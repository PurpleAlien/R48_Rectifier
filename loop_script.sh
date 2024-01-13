#!/bin/bash

# Define adapters
adapters=()
adapters+=("can0")
adapters+=("can1")

# Reconfigure all adapters
for adapter in "${adapters[@]}"
do
    echo "Re-initialize and re-configure adapter <$adapter>"
    sudo python ./rectifier.py --interface "$adapter" -C 
done

# Loop
while true
do
    for adapter in "${adapters[@]}"
    do
        python ./rectifier.py --mode "set" --interface "$adapter" --voltage 51.0 --current_value 50
        sleep 10
    done
done
