#!/bin/bash
set -e

echo "Starting ComfyUI server..."
cd /comfyui
python main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch &

echo "Waiting for ComfyUI to initialize..."
sleep 10

echo "Starting RunPod handler..."
cd /
python -u handler.py
