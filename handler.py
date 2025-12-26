import runpod
import json
import urllib.request
import urllib.parse
import base64
import time
import os

COMFY_API_URL = "http://127.0.0.1:8188"

def wait_for_comfy():
    """Wait for ComfyUI to be ready"""
    max_retries = 30
    for i in range(max_retries):
        try:
            urllib.request.urlopen(f"{COMFY_API_URL}/system_stats", timeout=5)
            print("ComfyUI is ready!")
            return True
        except:
            print(f"Waiting for ComfyUI... ({i+1}/{max_retries})")
            time.sleep(2)
    return False

def queue_prompt(prompt):
    """Queue a prompt to ComfyUI"""
    data = json.dumps({"prompt": prompt}).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_API_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
    response = urllib.request.urlopen(req)
    return json.loads(response.read())

def get_history(prompt_id):
    """Get the history/result of a prompt"""
    response = urllib.request.urlopen(f"{COMFY_API_URL}/history/{prompt_id}")
    return json.loads(response.read())

def get_image(filename, subfolder, folder_type):
    """Get generated image from ComfyUI"""
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    response = urllib.request.urlopen(f"{COMFY_API_URL}/view?{params}")
    return response.read()

def handler(job):
    """Main handler function for RunPod serverless"""
    job_input = job.get("input", {})
    
    # Get parameters from input
    prompt_text = job_input.get("prompt", "r3ligion, a man with short spiky green hair and a mustache, eating a slice of pizza in a futuristic neon city, cinematic lighting")
    image_base64 = job_input.get("image")  # Base64 encoded reference image
    guidance = job_input.get("guidance", 4.0)
    steps = job_input.get("steps", 15)
    width = job_input.get("width", 768)
    height = job_input.get("height", 1024)
    seed = job_input.get("seed", -1)  # -1 for random
    
    # Load the workflow
    workflow_path = "/comfyui/workflows/character_model_possesV1.json"
    with open(workflow_path, 'r') as f:
        workflow = json.load(f)
    
    # Modify workflow with input parameters
    # Node 6: CLIP Text Encode (prompt)
    workflow["6"]["inputs"]["text"] = prompt_text
    
    # Node 26: FluxGuidance
    workflow["26"]["inputs"]["guidance"] = guidance
    
    # Node 17: BasicScheduler (steps)
    workflow["17"]["inputs"]["steps"] = steps
    
    # Node 27: EmptySD3LatentImage (dimensions)
    workflow["27"]["inputs"]["width"] = width
    workflow["27"]["inputs"]["height"] = height
    
    # Node 25: RandomNoise (seed)
    if seed != -1:
        workflow["25"]["inputs"]["noise_seed"] = seed
    else:
        import random
        workflow["25"]["inputs"]["noise_seed"] = random.randint(0, 2**53)
    
    # Handle reference image
    if image_base64:
        # Save the image to ComfyUI input folder
        image_data = base64.b64decode(image_base64)
        input_image_path = "/comfyui/input/reference_image.png"
        with open(input_image_path, 'wb') as f:
            f.write(image_data)
        workflow["54"]["inputs"]["image"] = "reference_image.png"
    
    # Wait for ComfyUI to be ready
    if not wait_for_comfy():
        return {"error": "ComfyUI failed to start"}
    
    # Queue the prompt
    result = queue_prompt(workflow)
    prompt_id = result.get('prompt_id')
    
    if not prompt_id:
        return {"error": "Failed to queue prompt"}
    
    # Wait for completion
    max_wait = 300  # 5 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        history = get_history(prompt_id)
        if prompt_id in history:
            outputs = history[prompt_id].get('outputs', {})
            # Node 50 is PreviewImage
            if '50' in outputs and 'images' in outputs['50']:
                image_info = outputs['50']['images'][0]
                image_data = get_image(image_info['filename'], image_info.get('subfolder', ''), image_info['type'])
                return {
                    "image": base64.b64encode(image_data).decode('utf-8'),
                    "seed": workflow["25"]["inputs"]["noise_seed"],
                    "prompt": prompt_text
                }
        time.sleep(1)
    
    return {"error": "Timeout waiting for image generation"}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
