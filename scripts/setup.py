#!/usr/bin/env python3
"""
JARVIS V20 - Cross-Platform Python Installer
Run: python setup.py

Supports: Windows, Linux, macOS
"""
import sys
import subprocess
import shutil
import platform
from pathlib import Path

from colorama import init as colorama_init

colorama_init()

PROJECT_DIR = Path(__file__).parent.resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
OLLAMA_URL = "http://localhost:11434"
DEFAULT_RAM_GB = 8

BASE_MODELS = [
    "nomic-embed-text",
    "jobautomation/OpenEuroLLM-Czech:latest"
]


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"


def log_info(msg):
    print(f"{Colors.CYAN}{msg}{Colors.RESET}")


def log_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def log_warn(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def log_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def _detect_windows_ram_gb():
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)"
        ],
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)"
        ],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                value = float(result.stdout.strip().splitlines()[-1].replace(",", "."))
                if value > 0:
                    return max(1, int(round(value)))
        except Exception:
            continue

    try:
        result = subprocess.run(["systeminfo"], capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Total Physical Memory" in line:
                    raw_value = line.split(":", 1)[1].strip()
                    digits = "".join(ch for ch in raw_value if ch.isdigit())
                    if digits:
                        ram_mb = int(digits)
                        if ram_mb > 0:
                            return max(1, ram_mb // 1024)
    except Exception:
        pass

    return DEFAULT_RAM_GB


def detect_hardware():
    hardware_info = {
        "vram_gb": 0,
        "ram_gb": DEFAULT_RAM_GB,
        "cpu_name": platform.processor() or "Unknown CPU",
        "gpu_name": "No GPU detected"
    }

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            vram_mb = int(result.stdout.strip().split()[0])
            hardware_info["vram_gb"] = max(0, vram_mb // 1024)

            try:
                name_result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if name_result.returncode == 0 and name_result.stdout.strip():
                    hardware_info["gpu_name"] = name_result.stdout.strip()
            except Exception:
                pass
    except Exception:
        pass

    try:
        if platform.system() == "Windows":
            hardware_info["ram_gb"] = _detect_windows_ram_gb()
        else:
            result = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            hardware_info["ram_gb"] = max(1, int(parts[1]) // 1024)
                            break
    except Exception as exc:
        log_warn(f"Hardware detection fallback used: {exc}")

    if hardware_info["ram_gb"] <= 0:
        hardware_info["ram_gb"] = DEFAULT_RAM_GB

    return hardware_info


def recommend_models(vram_gb):
    if vram_gb < 4:
        return [
            ("qwen2.5:3b-instruct", "Lightweight, fast (best for low VRAM)"),
        ]
    elif vram_gb < 6:
        return [
            ("qwen2.5:7b-instruct", "Good balance"),
            ("llama3.1:8b-instruct-q4_K_M", "Better quality (quantized)"),
        ]
    elif vram_gb < 9:
        return [
            ("llama3.1:8b-instruct-q4_K_M", "RECOMMENDED - Best for 8GB VRAM"),
            ("llama3.1:8b-instruct-q5_K_M", "Higher quality, slower"),
            ("qwen2.5:7b-instruct", "Faster alternative"),
            ("gemma2:9b-instruct-q4_K_M", "Good for reasoning"),
        ]
    return [
        ("llama3.1:8b-instruct-q5_K_M", "Fast and capable"),
        ("llama3.1:8b-instruct", "Best quality 8B"),
        ("mistral-nemo:12b-instruct-q4_K_M", "Higher quality 12B"),
        ("llama3.1:70b-instruct-q4_K_M", "Best quality (slow, requires 8GB+)"),
    ]


def select_model(hardware_info):
    print()
    log_info("=" * 70)
    log_info("Hardware Detection Results:")
    log_info("=" * 70)
    print(f"  GPU:  {hardware_info['gpu_name']}")
    if hardware_info['vram_gb'] > 0:
        print(f"  VRAM: {hardware_info['vram_gb']} GB")
    else:
        print("  VRAM: Not detected (or no NVIDIA GPU)")
    if hardware_info['ram_gb'] > 0:
        print(f"  RAM:  {hardware_info['ram_gb']} GB")
    print()
    log_info("=" * 70)
    log_info("Recommended models for your system:")
    log_info("=" * 70)
    print()

    recommendations = recommend_models(hardware_info['vram_gb'])

    for i, (model, desc) in enumerate(recommendations, 1):
        print(f"  [{i}] {model}")
        print(f"      {desc}")
        print()

    print(f"  [{len(recommendations) + 1}] Custom - Enter your own model name")
    print()

    while True:
        try:
            choice = input(f"Select [1-{len(recommendations) + 1}]: ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(recommendations):
                selected_model = recommendations[choice_num - 1][0]
                log_success(f"Selected: {selected_model}")
                return selected_model
            if choice_num == len(recommendations) + 1:
                while True:
                    custom_model = input("Enter model name (e.g., llama3.1:8b-instruct): ").strip()
                    if custom_model:
                        log_success(f"Selected: {custom_model}")
                        return custom_model
                    log_error("Please enter a model name")
            else:
                log_error(f"Please enter a number between 1 and {len(recommendations) + 1}")
        except ValueError:
            log_error("Please enter a valid number")
        except KeyboardInterrupt:
            log_error("\nSetup cancelled")
            sys.exit(1)


def update_user_config(model):
    config_path = PROJECT_DIR / "jarvis_config" / "user_config.py"

    config_content = f'''"""
User Configuration Override for JARVIS

This file was auto-generated by the setup script based on your
detected hardware and selected model preferences.

You can also edit this file manually to change model settings.
"""

def apply_user_config():
    """Apply user-selected model configuration."""
    import jarvis_config as _cfg

    _cfg.MODELS["planner"] = "{model}"
    _cfg.MODELS["verifier"] = "{model}"
    _cfg.MODELS["reasoner"] = "{model}"
'''

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        log_success(f"Configuration updated: {config_path}")
        return True
    except Exception as e:
        log_error(f"Failed to update configuration: {e}")
        return False


def run_cmd(cmd, check=True, capture=True, shell=False):
    try:
        if isinstance(cmd, str):
            if shell:
                result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
            else:
                result = subprocess.run(cmd.split(), capture_output=capture, text=True)
        else:
            result = subprocess.run(cmd, capture_output=capture, text=True)

        if check and result.returncode != 0:
            if result.stderr:
                log_error(f"Command failed: {result.stderr.strip()}")
            return False, result
        return True, result
    except (FileNotFoundError, Exception):
        return False, None


def is_ollama_running():
    try:
        import requests
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def install_ollama():
    system = sys.platform
    log_warn("Ollama is not installed. Installing...")

    if system == "win32":
        log_info("For Windows:")
        log_info("  1. Download: https://ollama.com/download/windows")
        log_info("  2. Run OllamaSetup.exe")
        log_info("  3. Restart this script")
        log_info("\nOr use winget: winget install Ollama.Ollama")
        return False
    if system == "darwin":
        if shutil.which("brew"):
            log_info("Installing Ollama via Homebrew...")
            run_cmd(["brew", "install", "ollama"], check=False)
            run_cmd(["brew", "services", "start", "ollama"], check=False)
            return True
        log_info("For macOS:")
        log_info("  1. Download: https://ollama.com/download/mac")
        log_info("  2. Install the .app")
        return False

    if shutil.which("curl"):
        log_info("Installing Ollama via official script...")
        success, _ = run_cmd("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=False)
        if success:
            run_cmd(["ollama", "serve"], check=False)
            return True
        return False

    log_error("curl is required to install Ollama")
    return False


def wait_for_ollama(timeout=60):
    log_info("Waiting for Ollama service...")
    import time
    start = time.time()
    while time.time() - start < timeout:
        if is_ollama_running():
            return True
        time.sleep(2)
    return False


def pull_model(model):
    log_info(f"Downloading model: {model}")
    log_info("  (This may take several minutes...)")
    success, _ = run_cmd(["ollama", "pull", model], check=False)
    if success:
        log_success(f"Model installed: {model}")
        return True
    log_error(f"Failed to install: {model}")
    return False


def create_data_dirs():
    log_info("Creating JARVIS data directories...")
    dirs = [
        "jarvis_data/memory",
        "jarvis_data/orchestrator",
        "jarvis_data/chromadb",
        "jarvis_data/knowledge_graph",
        "jarvis_data/wal",
        "jarvis_data/procedural"
    ]
    for d in dirs:
        (PROJECT_DIR / d).mkdir(parents=True, exist_ok=True)
    log_success("Directories created")


def check_python():
    version = sys.version_info
    return version.major >= 3 and version.minor >= 10


def install_dependencies(python_cmd):
    log_info("Installing Python dependencies...")
    run_cmd([python_cmd, "-m", "pip", "install", "--upgrade", "pip"], check=False)
    req_file = PROJECT_DIR / "requirements.txt"
    run_cmd([python_cmd, "-m", "pip", "install", "-r", str(req_file)], check=False)
    log_success("Dependencies installed")


def test_jarvis(python_cmd):
    log_info("Testing JARVIS...")
    success, _ = run_cmd([python_cmd, str(PROJECT_DIR / "main.py"), "--help"], check=False)
    if success:
        log_success("JARVIS is ready!")
        return True
    return False


def print_banner():
    print(f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════╗
║          🤖 JARVIS V20 - Universal Setup Installer            ║
║              Cross-Platform Python Edition                    ║
╚═══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def main():
    print_banner()
    log_info("[1/7] Checking Python installation...")

    if not check_python():
        log_error("Python 3.10+ required!")
        print(f"  Current: {sys.version}")
        print("\nPlease install Python 3.10 or higher from https://python.org/")
        return 1

    log_success(f"Python {sys.version_info.major}.{sys.version_info.minor} found")
    python_cmd = "python" if sys.platform == "win32" else "python3"

    log_info("[2/7] Setting up virtual environment...")
    if VENV_DIR.exists():
        log_info("Virtual environment already exists")
    else:
        run_cmd([python_cmd, "-m", "venv", str(VENV_DIR)], check=False)
        log_success("Virtual environment created")

    if sys.platform == "win32":
        venv_python = str(VENV_DIR / "Scripts" / "python.exe")
    else:
        venv_python = str(VENV_DIR / "bin" / "python")

    log_info("[3/7] Installing Python dependencies...")
    install_dependencies(venv_python)

    log_info("[4/7] Checking Ollama...")
    if not is_ollama_running():
        if not shutil.which("ollama"):
            if not install_ollama():
                log_error("Could not install Ollama automatically")
                log_info("Please install Ollama manually and re-run this script")
                return 1
        else:
            log_warn("Ollama installed but not running. Starting...")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not wait_for_ollama():
                log_error("Ollama failed to start")
                return 1

    log_success("Ollama is running")

    log_info("[5/7] Detecting hardware and selecting model...")
    hardware_info = detect_hardware()
    selected_model = select_model(hardware_info)

    log_info("[6/7] Downloading LLM models...")
    print()
    log_warn("  Model sizes (approximate):")
    print("  - nomic-embed-text:       ~274 MB")
    print("  - OpenEuroLLM-Czech:      ~4-5 GB")
    print(f"  - {selected_model}:      ~2-10 GB (varies by model)")
    print()
    log_warn("  This will take a while depending on your internet speed...")
    print()

    for model in BASE_MODELS:
        if not pull_model(model):
            log_error(f"Failed to pull model: {model}")
            return 1
        print()

    if not pull_model(selected_model):
        log_error(f"Failed to pull model: {selected_model}")
        return 1
    print()

    if not update_user_config(selected_model):
        log_warn("Failed to update configuration. You may need to edit jarvis_config/user_config.py manually")

    log_info("[7/7] Creating data directories...")
    create_data_dirs()

    print()
    test_jarvis(venv_python)

    print()
    log_success("════════════════════════════════════════════════════════════")
    log_success("  🎉 INSTALLATION COMPLETE!")
    log_success("════════════════════════════════════════════════════════════")
    print()
    print("  Configuration:")
    print(f"  - Selected model: {selected_model}")
    print("  - Czech gateway:  OpenEuroLLM-Czech:latest")
    print()
    print("  Next steps:")
    if sys.platform == "win32":
        print("  1. Run: scripts\\start_jarvis.bat")
    else:
        print("  1. Run: ./scripts/run.sh")
    print(f"  2. Or:  {venv_python} main.py")
    print()
    print("  First run will initialize the vector database...")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
