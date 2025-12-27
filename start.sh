#!/bin/bash
set -e

echo "=========================================="
echo "Starting ComfyUI PuLID-Flux Worker"
echo "=========================================="

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

download_if_missing "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors" "/comfyui/models/checkpoints/flux1-dev-fp8.safetensors"

download_if_missing "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" "/comfyui/models/clip/t5xxl_fp8_e4m3fn.safetensors"

download_if_missing "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" "/comfyui/models/clip/clip_l.safetensors"

download_if_missing "https://huggingface.co/sirorable/flux-ae-vae/resolve/main/ae.safetensors" "/comfyui/models/vae/ae.safetensors"

download_if_missing "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors" "/comfyui/models/pulid/pulid_flux_v0.9.1.safetensors"

curl_download_if_missing "https://civitai.com/api/download/models/2323899?type=Model&format=SafeTensor&token=2e9070f392c2365690954ed44def8fc4" "/comfyui/models/loras/SoftLineart.safetensors"

# InsightFace models - download and extract correctly
if [ ! -f "/root/.insightface/models/antelopev2/scrfd_10g_bnkps.onnx" ]; then
    echo "Downloading InsightFace models..."
    mkdir -p /root/.insightface/models
    mkdir -p /comfyui/models/insightface/models
    cd /root/.insightface/models
    wget -q "https://huggingface.co/MonsterMMORPG/tools/resolve/main/antelopev2.zip"
    unzip -o antelopev2.zip
    rm antelopev2.zip
    
    # Check where files ended up
    echo "Checking extraction..."
    ls -la /root/.insightface/models/
    ls -la /root/.insightface/models/antelopev2/
    
    # Verify the detection model exists
    if [ ! -f "/root/.insightface/models/antelopev2/scrfd_10g_bnkps.onnx" ]; then
        echo "ERROR: InsightFace models not in expected location"
        find /root/.insightface -name "*.onnx" 2>/dev/null
        exit 1
    fi
    
    # Copy to comfyui location
    cp -r /root/.insightface/models/antelopev2 /comfyui/models/insightface/models/
    cd /
    echo "InsightFace models installed successfully"
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
