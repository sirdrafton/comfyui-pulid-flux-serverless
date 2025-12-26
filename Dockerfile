FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    git \
    wget \
    curl \
    unzip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set python3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Install PyTorch with CUDA 12.1
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui

WORKDIR /comfyui
RUN pip install --no-cache-dir -r requirements.txt

# Install RunPod SDK and dependencies
RUN pip install --no-cache-dir runpod insightface onnxruntime-gpu opencv-python scikit-image facexlib

# Create directories
RUN mkdir -p models/checkpoints models/loras models/pulid models/clip models/vae models/insightface/models input output workflows

# Download Flux checkpoint
RUN wget -q -O models/checkpoints/flux1-dev-fp8.safetensors \
    "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors"

# Download T5 encoder
RUN wget -q -O models/clip/t5xxl_fp8_e4m3fn.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"

# Download CLIP
RUN wget -q -O models/clip/clip_l.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"

# Download VAE
RUN wget -q -O models/vae/ae.safetensors \
    "https://huggingface.co/sirorable/flux-ae-vae/resolve/main/ae.safetensors"

# Download PuLID
RUN wget -q -O models/pulid/pulid_flux_v0.9.1.safetensors \
    "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors"

# Download LoRA from CivitAI
ARG CIVITAI_TOKEN=2e9070f392c2365690954ed44def8fc4
RUN curl -L -o models/loras/SoftLineart.safetensors \
    "https://civitai.com/api/download/models/2323899?type=Model&format=SafeTensor&token=${CIVITAI_TOKEN}"

# Download InsightFace antelopev2
RUN mkdir -p models/insightface/models/antelopev2 && \
    wget -q -O models/insightface/models/antelopev2/antelopev2.zip \
    "https://huggingface.co/MonsterMMORPG/tools/resolve/main/antelopev2.zip" && \
    cd models/insightface/models/antelopev2 && unzip antelopev2.zip && rm antelopev2.zip

# Copy custom nodes
COPY custom_nodes/ /comfyui/custom_nodes/

# Install custom node requirements
RUN for dir in /comfyui/custom_nodes/*/; do \
    if [ -f "${dir}requirements.txt" ]; then \
        pip install --no-cache-dir -r "${dir}requirements.txt" || true; \
    fi \
done

# Copy workflows, handler, and start script
COPY workflows/ /comfyui/workflows/
COPY handler.py /handler.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

WORKDIR /
EXPOSE 8188
CMD ["/start.sh"]
