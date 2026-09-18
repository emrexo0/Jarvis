"""
JARVIS v2 – Configuration, paths and constants
"""
import os
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("JARVIS")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # artifacts/
# If running from jarvis_v2 itself, adjust
if os.path.basename(BASE_DIR) == "jarvis_v2":
    BASE_DIR = os.path.dirname(BASE_DIR)

MODELS_DIR = os.path.join(BASE_DIR, "models")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.txt")
CONFIG_FILE = os.path.join(BASE_DIR, "jarvis_config.json")
CHATS_DIR = os.path.join(BASE_DIR, "chats")
TTS_DIR = os.path.join(MODELS_DIR, "jarvis")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
BACKGROUNDS_DIR = os.path.join(BASE_DIR, "backgrounds")

DEFAULT_MODEL_NAME = "Llama-3.2-3B-Instruct-uncensored-Q4_K_M.gguf"
DEFAULT_MODEL_PATH = os.path.join(MODELS_DIR, DEFAULT_MODEL_NAME)

# User-provided Qwen3-VL
DEFAULT_VISION_MODEL = "Qwen3VL-8B-Instruct-Q8_0.gguf"
DEFAULT_VISION_MMPROJ = "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
DEFAULT_VISION_PATH = os.path.join(MODELS_DIR, DEFAULT_VISION_MODEL)
DEFAULT_MMPROJ_PATH = os.path.join(MODELS_DIR, DEFAULT_VISION_MMPROJ)

PIPER_MODEL = "jarvis-high.onnx"
PIPER_CONFIG = "jarvis-high.onnx.json"

COMMAND_FLAG_FILE = os.path.join(BASE_DIR, "jarvis_command.flag")

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
BACKGROUND_EXTENSIONS = {".mp4", ".gif", ".png", ".jpg", ".jpeg"}

for d in (CHATS_DIR, CACHE_DIR, TEMP_DIR, BACKGROUNDS_DIR, MODELS_DIR):
    os.makedirs(d, exist_ok=True)

if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(
            "System Name: JARVIS\n"
            "Version: 2.0 Advanced\n"
            "Owner: User\n"
            "Architecture: Modular (Brain + Eyes + Hands)\n"
            "Base: Text GGUF + Vision GGUF (Qwen3-VL) + continuous screen awareness\n"
        )

# Soft palette
STAR_COLORS = ["#0a1628", "#0d1e36", "#102848", "#13305a", "#1a3a6a"]
DUST_BASE = (30, 90, 160)
SUPERNOVA_COLORS = ["#ff6b35", "#ff9f1c", "#ffbf69", "#ffffff", "#a0e7ff", "#7bdff2"]

FILLER_PHRASES = [
    "On it, sir.", "Right away.", "Hold on a second...", "Processing your request.",
    "Just a moment.", "Analyzing...", "Accessing systems...", "One moment, sir.",
    "Certainly.", "At once.", "Browsing for you now.", "Thinking...",
    "Sure thing, give me a second.", "Retrieving information...", "Working on that."
]

# ── Config helpers ──────────────────────────────────────────────────────────
def load_config():
    defaults = {
        "text_model_path": DEFAULT_MODEL_PATH,
        "vision_model_path": DEFAULT_VISION_PATH,
        "vision_mmproj_path": DEFAULT_MMPROJ_PATH,
        "piper_model_path": os.path.join(TTS_DIR, PIPER_MODEL),
        "piper_config_path": os.path.join(TTS_DIR, PIPER_CONFIG),
        "tts_engine": "system",
        "background_path": "",
        "background_active": False,
        "speech_volume": 0.85,
        "sfx_volume": 0.8,
        "bg_volume": 0.6,
        "vision_interval_sec": 4.0,          # how often the eyes look
        "vision_enabled": True,
        "agent_mode": True,                 # no-command / model decides everything
        "last_chat_id": None,
    }
    if not os.path.exists(CONFIG_FILE):
        return defaults
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return defaults


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logger.warning(f"Config save failed: {e}")
