import runpod
import json
import requests
import time
import base64
import random

COMFY_API_URL = "http://127.0.0.1:8188"

def wait_for_comfyui(max_retries=30, delay=2):
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMFY_API_URL}/system_stats")
            if response.status_code == 200:
                print("ComfyUI is ready!")
                return True
        except:
            pass
        print(f"Waiting for ComfyUI... ({i+1}/{max_retries})")
        time.sleep(delay)
    return False

def handler(job):
    job_input = job.get("input", {})
    
    prompt_text = job_input.get("prompt", "a beautiful woman, portrait")
    negative_prompt = job_input.get("negative_prompt", "text, watermark")
    steps = job_input.get("steps", 20)
    cfg = job_input.get("cfg", 1)
    width = job_input.get("width", 1024)
    height = job_input.get("height", 1024)
    seed = job_input.get("seed", -1)
    
    if seed == -1:
        seed = random.randint(0, 2**32 - 1)
    
    if not wait_for_comfyui():
        return {"error": "ComfyUI failed to start"}
    
    with open("/comfyui/workflows/CreateCharacterBeingV1.json", "r") as f:
        workflow = json.load(f)
    
    workflow["3"]["inputs"]["seed"] = seed
    workflow["3"]["inputs"]["steps"] = steps
    workflow["3"]["inputs"]["cfg"] = cfg
    workflow["5"]["inputs"]["width"] = width
    workflow["5"]["inputs"]["height"] = height
    workflow["6"]["inputs"]["text"] = prompt_text
    workflow["7"]["inputs"]["text"] = negative_prompt
    
    try:
        response = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
        result = response.json()
        prompt_id = result.get("prompt_id")
        
        if not prompt_id:
            return {"error": "Failed to queue prompt", "details": result}
        
        for _ in range(300):
            history = requests.get(f"{COMFY_API_URL}/history/{prompt_id}").json()
            
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                
                for node_id, node_output in outputs.items():
                    if "images" in node_output and node_output["images"]:
                        img = node_output["images"][0]
                        img_data = requests.get(
                            f"{COMFY_API_URL}/view",
                            params={"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")}
                        ).content
                        
                        return {
                            "status": "success",
                            "image": base64.b64encode(img_data).decode("utf-8"),
                            "seed": seed,
                            "prompt": prompt_text
                        }
                
                if history[prompt_id].get("status", {}).get("status_str") == "error":
                    return {"error": "Workflow failed", "details": history[prompt_id]}
            
            time.sleep(1)
        
        return {"error": "Timeout waiting for generation"}
        
    except Exception as e:
        return {"error": str(e)}

runpod.serverless.start({"handler": handler})
