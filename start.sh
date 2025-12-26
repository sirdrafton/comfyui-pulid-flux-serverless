#!/bin/bash
set -e

echo "=========================================="
echo "Starting ComfyUI PuLID-Flux Worker"
echo "=========================================="

# Function to download if file doesn't exist
download_if_missing() {
    local url=$1
    local dest=$2
    if [ ! -f "$dest" ]; then
        echo "Downloading: $dest"
        wget -q --show-progress -O "$dest" "$url"
    else
        echo "Already exists: $dest"
    fi
}

# Function to download with curl (for CivitAI)
curl_download_if_missing() {
    local url=$1
    local dest=$2
    if [ ! -f "$dest" ]; then
        echo "Downloading: $dest"
        curl -L -o "$dest" "$url"
    else
        echo "Already exists: $dest"
    fi
}

echo "Checking/downloading models..."

# Download models if they don't exist
download_if_missing "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors" "/comfyui/models/checkpoints/flux1-dev-fp8.safetensors"

download_if_missing "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" "/comfyui/models/clip/t5xxl_fp8_e4m3fn.safetensors"

download_if_missing "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" "/comfyui/models/clip/clip_l.safetensors"

download_if_missing "https://huggingface.co/sirorable/flux-ae-vae/resolve/main/ae.safetensors" "/comfyui/models/vae/ae.safetensors"

download_if_missing "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors" "/comfyui/models/pulid/pulid_flux_v0.9.1.safetensors"

# CivitAI LoRA
curl_download_if_missing "https://civitai.com/api/download/models/2323899?type=Model&format=SafeTensor&token=2e9070f392c2365690954ed44def8fc4" "/comfyui/models/loras/SoftLineart.safetensors"

# InsightFace models
if [ ! -d "/comfyui/models/insightface/models/antelopev2" ] || [ -z "$(ls -A /comfyui/models/insightface/models/antelopev2 2>/dev/null)" ]; then
    echo "Downloading InsightFace models..."
    mkdir -p /comfyui/models/insightface/models/antelopev2
    cd /comfyui/models/insightface/models/antelopev2
    wget -q "https://huggingface.co/MonsterMMORPG/tools/resolve/main/antelopev2.zip"
    unzip -o antelopev2.zip
    rm antelopev2.zip
    cd /
else
    echo "Already exists: InsightFace models"
fi

echo "All models ready!"
echo "=========================================="

echo "Starting ComfyUI server..."
cd /comfyui
python main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch &

echo "Waiting for ComfyUI to initialize..."
sleep 10

echo "Starting RunPod handler..."
cd /
python -u /handler.py
