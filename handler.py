import runpod
import json
import requests
import time
import base64
import random
import os

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

def save_input_images(images_dict):
    """Save base64 images to ComfyUI input folder, return filename mapping"""
    saved = {}
    for name, base64_data in images_dict.items():
        try:
            image_data = base64.b64decode(base64_data)
            filename = f"input_{name}.png"
            filepath = f"/comfyui/input/{filename}"
            with open(filepath, "wb") as f:
                f.write(image_data)
            saved[name] = filename
            print(f"Saved input image: {filename}")
        except Exception as e:
            print(f"Failed to save image {name}: {e}")
    return saved

def apply_modifications(workflow, modifications, input_images=None):
    """Apply modifications to workflow nodes"""
    for node_id, changes in modifications.items():
        node_id_str = str(node_id)
        if node_id_str in workflow:
            for key, value in changes.items():
                # Handle image references
                if input_images and value in input_images:
                    value = input_images[value]
                workflow[node_id_str]["inputs"][key] = value
                print(f"Modified node {node_id_str}: {key} = {value}")
        else:
            print(f"Warning: Node {node_id_str} not found in workflow")
    return workflow

def find_output_images(history, prompt_id):
    """Extract output images from ComfyUI history"""
    images = []
    if prompt_id in history:
        outputs = history[prompt_id].get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    img_data = requests.get(
                        f"{COMFY_API_URL}/view",
                        params={
                            "filename": img["filename"],
                            "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output")
                        }
                    ).content
                    images.append({
                        "node_id": node_id,
                        "filename": img["filename"],
                        "data": base64.b64encode(img_data).decode("utf-8")
                    })
    return images

def handler(job):
    """
    Universal ComfyUI workflow handler
    
    Input format:
    {
        "workflow_json": { ... ComfyUI API format workflow ... },
        "modifications": {
            "node_id": {"input_name": "value", ...},
            ...
        },
        "images": {
            "image_name": "base64_encoded_image_data",
            ...
        }
    }
    
    The modifications dict lets you override any node input.
    The images dict lets you upload images that can be referenced in modifications.
    """
    job_input = job.get("input", {})
    
    # Get workflow - required
    workflow = job_input.get("workflow_json") or job_input.get("workflow")
    if not workflow:
        return {"error": "No workflow provided. Send 'workflow_json' with your ComfyUI API-format workflow."}
    
    # Get optional modifications
    modifications = job_input.get("modifications", {})
    
    # Get optional input images
    input_images_b64 = job_input.get("images", {})
    
    # Wait for ComfyUI
    if not wait_for_comfyui():
        return {"error": "ComfyUI failed to start"}
    
    # Save any input images
    saved_images = {}
    if input_images_b64:
        saved_images = save_input_images(input_images_b64)
    
    # Apply modifications
    if modifications:
        workflow = apply_modifications(workflow, modifications, saved_images)
    
    # Generate random seed for any seed fields set to -1
    for node_id, node in workflow.items():
        if isinstance(node, dict) and "inputs" in node:
            inputs = node["inputs"]
            for key in ["seed", "noise_seed"]:
                if key in inputs and inputs[key] == -1:
                    inputs[key] = random.randint(0, 2**32 - 1)
                    print(f"Generated random seed for node {node_id}: {inputs[key]}")
    
    # Queue the prompt
    try:
        response = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
        result = response.json()
        
        if "error" in result:
            return {"error": "ComfyUI rejected workflow", "details": result}
        
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            return {"error": "Failed to queue prompt", "details": result}
        
        print(f"Queued prompt: {prompt_id}")
        
        # Wait for completion (5 min timeout)
        for i in range(300):
            history = requests.get(f"{COMFY_API_URL}/history/{prompt_id}").json()
            
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                status_str = status.get("status_str", "")
                
                if status_str == "error":
                    return {
                        "error": "Workflow execution failed",
                        "details": history[prompt_id]
                    }
                
                # Check if we have outputs
                outputs = history[prompt_id].get("outputs", {})
                if outputs:
                    images = find_output_images(history, prompt_id)
                    if images:
                        return {
                            "status": "success",
                            "images": images,
                            "prompt_id": prompt_id
                        }
            
            time.sleep(1)
        
        return {"error": "Timeout waiting for generation (5 min)"}
        
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

runpod.serverless.start({"handler": handler})
