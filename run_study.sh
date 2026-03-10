#!/bin/bash

read -p "Algorithm (random/bald): " choice

case "$choice" in
    random|1) cp config_random.json config.json ;;
    bald|2) cp config_bald.json config.json ;;
    *) echo "Invalid"; exit 1 ;;
esac

python3 app.py
