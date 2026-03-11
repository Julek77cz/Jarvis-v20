"""Dynamic hardware-aware configuration for JARVIS."""
import logging
import platform

logger = logging.getLogger("JARVIS.CONFIG.DYNAMIC")


def apply_hardware_scaling():
    """Apply hardware-specific scaling based on detected VRAM and RAM."""
    import subprocess
    
    # Default conservative values
    vram_gb = 0
    ram_gb = 8
    gpu_name = "No GPU"
    
    try:
        # Detect VRAM using nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                vram_mb = int(result.stdout.strip().split()[0])
                vram_gb = vram_mb // 1024
                
                # Get GPU name
                name_result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=10
                )
                if name_result.returncode == 0:
                    gpu_name = name_result.stdout.strip()
        except:
            pass
        
        # Detect RAM
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "OS", "get", "TotalVisibleMemorySize", "/value"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'TotalVisibleMemorySize':
                                ram_kb = int(value.strip())
                                ram_gb = ram_kb // (1024 * 1024)
                                break
            else:
                result = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('Mem:'):
                            parts = line.split()
                            if len(parts) >= 2:
                                ram_gb = int(parts[1]) // 1024
                                break
        except:
            pass
            
    except Exception as e:
        print(f"[HW] Detection error: {e}, using conservative CPU values")
    
    # ===== MODEL SELECTION =====
    try:
        import os
        import jarvis_config as _cfg
        user_config_path = os.path.join(os.path.dirname(__file__), "user_config.py")
        # Check if user already has custom models (skip if override exists)
        if os.path.exists(user_config_path):
            with open(user_config_path, 'r') as f:
                content = f.read()
                if 'MODELS' in content and 'apply_user_config' in content:
                    print("[HW] User has custom model config, skipping auto-selection")
                else:
                    # Auto-select model based on VRAM
                    if vram_gb < 4 or vram_gb == 0:
                        selected_model = "qwen2.5:3b-instruct"
                    elif vram_gb < 8:
                        selected_model = "qwen2.5:3b-instruct"
                    elif vram_gb < 16:
                        selected_model = "qwen2.5:7b-instruct-q4_K_M"
                    else:
                        selected_model = "qwen2.5:14b-instruct-q4_K_M"
                    
                    # Apply to MODELS (planner/verifier/reasoner)
                    _cfg.MODELS["planner"] = selected_model
                    _cfg.MODELS["verifier"] = selected_model
                    _cfg.MODELS["reasoner"] = selected_model
    except:
        pass
    
    # ===== DYNAMIC HW_OPTIONS =====
    if vram_gb == 0:  # No GPU / CPU only
        HW_OPTIONS = {
            "num_gpu": 0,
            "num_ctx": 2048,
            "num_batch": 128,
            "num_predict": 512,
            "temperature": 0.7,
        }
    elif vram_gb < 8:
        HW_OPTIONS = {
            "num_gpu": 20,
            "num_ctx": 4096,
            "num_batch": 256,
            "num_predict": 1024,
            "temperature": 0.7,
        }
    elif vram_gb < 16:
        HW_OPTIONS = {
            "num_gpu": 35,
            "num_ctx": 8192,
            "num_batch": 512,
            "num_predict": 2048,
            "temperature": 0.7,
        }
    else:  # 16GB+
        HW_OPTIONS = {
            "num_gpu": 50,
            "num_ctx": 16384,
            "num_batch": 1024,
            "num_predict": 4096,
            "temperature": 0.7,
        }
    
    # ===== DYNAMIC SWARM_MAX_AGENTS =====
    # Without GPU or RAM <8GB → 1 agent
    # GPU + RAM 8-32GB → 2 agents
    # GPU + RAM 32GB+ → 4 agents
    if vram_gb == 0 or ram_gb < 8:
        SWARM_MAX_AGENTS = 1
    elif ram_gb >= 32 and vram_gb > 0:
        SWARM_MAX_AGENTS = 4
    else:
        SWARM_MAX_AGENTS = 2
    
    return {
        "vram_gb": vram_gb,
        "ram_gb": ram_gb,
        "gpu_name": gpu_name,
        "hw_options": HW_OPTIONS,
        "swarm_max_agents": SWARM_MAX_AGENTS,
    }
