import runpod
import json
import requests
import time
import base64
import os

# ComfyUI API endpoint
COMFY_API_URL = "http://127.0.0.1:8188"

def wait_for_comfyui(max_retries=30, delay=2):
    """Wait for ComfyUI to be ready"""
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMFY_API_URL}/system_stats")
            if response.status_code == 200:
                print("ComfyUI is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        print(f"Waiting for ComfyUI... ({i+1}/{max_retries})")
        time.sleep(delay)
    return False

def load_workflow():
    """Load the workflow JSON file"""
    workflow_path = "/comfyui/workflows/character_model_possesV1.json"
    with open(workflow_path, 'r') as f:
        return json.load(f)

def convert_to_api_format(workflow_data):
    """Convert frontend workflow format to API format"""
    if "nodes" not in workflow_data:
        # Already in API format
        return workflow_data
    
    api_workflow = {}
    nodes = workflow_data.get("nodes", [])
    links = workflow_data.get("links", [])
    
    # Create a mapping of link_id to [source_node, source_slot]
    link_map = {}
    for link in links:
        # link format: [link_id, source_node, source_slot, target_node, target_slot, type]
        link_id = link[0]
        source_node = link[1]
        source_slot = link[2]
        link_map[link_id] = [str(source_node), source_slot]
    
    for node in nodes:
        node_id = str(node.get("id"))
        node_type = node.get("type")
        
        # Get widgets_values as inputs
        inputs = {}
        widgets_values = node.get("widgets_values", [])
        
        # Get input connections
        node_inputs = node.get("inputs", [])
        for inp in node_inputs:
            inp_name = inp.get("name")
            link_id = inp.get("link")
            if link_id is not None and link_id in link_map:
                inputs[inp_name] = link_map[link_id]
        
        # Map widgets_values to input names based on node type
        # This is node-type specific
        if node_type == "CLIPTextEncode" and len(widgets_values) >= 1:
            inputs["text"] = widgets_values[0]
        elif node_type == "EmptySD3LatentImage" and len(widgets_values) >= 3:
            inputs["width"] = widgets_values[0]
            inputs["height"] = widgets_values[1]
            inputs["batch_size"] = widgets_values[2]
        elif node_type == "RandomNoise" and len(widgets_values) >= 1:
            inputs["noise_seed"] = widgets_values[0]
        elif node_type == "FluxGuidance" and len(widgets_values) >= 1:
            inputs["guidance"] = widgets_values[0]
        elif node_type == "BasicScheduler" and len(widgets_values) >= 3:
            inputs["scheduler"] = widgets_values[0]
            inputs["steps"] = widgets_values[1]
            inputs["denoise"] = widgets_values[2]
        elif node_type == "LoadImage" and len(widgets_values) >= 1:
            inputs["image"] = widgets_values[0]
        
        api_workflow[node_id] = {
            "class_type": node_type,
            "inputs": inputs
        }
    
    return api_workflow

def queue_prompt(workflow):
    """Queue a prompt to ComfyUI"""
    payload = {"prompt": workflow}
    response = requests.post(f"{COMFY_API_URL}/prompt", json=payload)
    return response.json()

def get_history(prompt_id):
    """Get the history for a prompt"""
    response = requests.get(f"{COMFY_API_URL}/history/{prompt_id}")
    return response.json()

def get_image(filename, subfolder, folder_type):
    """Get an image from ComfyUI"""
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    response = requests.get(f"{COMFY_API_URL}/view", params=params)
    return response.content

def handler(job):
    """RunPod serverless handler"""
    job_input = job.get("input", {})
    
    # Get input parameters
    prompt_text = job_input.get("prompt", "a beautiful landscape")
    image_base64 = job_input.get("image")  # Optional base64 image for PuLID
    guidance = job_input.get("guidance", 4.0)
    steps = job_input.get("steps", 20)
    width = job_input.get("width", 1024)
    height = job_input.get("height", 1024)
    seed = job_input.get("seed", -1)
    
    if seed == -1:
        import random
        seed = random.randint(0, 2**32 - 1)
    
    # Wait for ComfyUI to be ready
    if not wait_for_comfyui():
        return {"error": "ComfyUI failed to start"}
    
    # Load and convert workflow
    workflow_data = load_workflow()
    workflow = convert_to_api_format(workflow_data)
    
    # Modify workflow with input parameters
    # Node 6: CLIPTextEncode (prompt)
    if "6" in workflow:
        workflow["6"]["inputs"]["text"] = prompt_text
    
    # Node 27: EmptySD3LatentImage (dimensions)
    if "27" in workflow:
        workflow["27"]["inputs"]["width"] = width
        workflow["27"]["inputs"]["height"] = height
    
    # Node 25: RandomNoise (seed)
    if "25" in workflow:
        workflow["25"]["inputs"]["noise_seed"] = seed
    
    # Node 26: FluxGuidance (guidance)
    if "26" in workflow:
        workflow["26"]["inputs"]["guidance"] = guidance
    
    # Node 17: BasicScheduler (steps)
    if "17" in workflow:
        workflow["17"]["inputs"]["steps"] = steps
    
    # Handle input image for PuLID if provided
    if image_base64:
        # Save image to ComfyUI input folder
        image_data = base64.b64decode(image_base64)
        image_path = "/comfyui/input/input_image.png"
        with open(image_path, "wb") as f:
            f.write(image_data)
        
        # Node 54: LoadImage
        if "54" in workflow:
            workflow["54"]["inputs"]["image"] = "input_image.png"
    
    # Queue the prompt
    try:
        result = queue_prompt(workflow)
        prompt_id = result.get("prompt_id")
        
        if not prompt_id:
            return {"error": "Failed to queue prompt", "details": result}
        
        # Wait for completion
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            history = get_history(prompt_id)
            
            if prompt_id in history:
                prompt_history = history[prompt_id]
                
                if "outputs" in prompt_history:
                    outputs = prompt_history["outputs"]
                    
                    # Find the PreviewImage or SaveImage node output
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            images = node_output["images"]
                            if images:
                                image_info = images[0]
                                image_data = get_image(
                                    image_info["filename"],
                                    image_info.get("subfolder", ""),
                                    image_info.get("type", "output")
                                )
                                
                                # Return base64 encoded image
                                image_base64_out = base64.b64encode(image_data).decode("utf-8")
                                return {
                                    "status": "success",
                                    "image": image_base64_out,
                                    "seed": seed,
                                    "prompt": prompt_text
                                }
                
                # Check for errors
                if prompt_history.get("status", {}).get("status_str") == "error":
                    return {"error": "Workflow execution failed", "details": prompt_history}
            
            time.sleep(1)
        
        return {"error": "Timeout waiting for image generation"}
        
    except Exception as e:
        return {"error": str(e)}

# Start the serverless worker
runpod.serverless.start({"handler": handler})
