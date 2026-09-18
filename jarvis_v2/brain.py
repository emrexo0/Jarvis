"""
JARVIS v2 – Brain
- Text and vision models load independently (never both at once during load)
- Inference lock: Brain and Eyes take turns (no simultaneous GGUF runs)
- Vision is only used when the request needs it
"""
import os
import re
import json
import time
import threading
import random
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any

from .config import (
    logger, MEMORY_FILE, load_config, save_config,
    FILLER_PHRASES, MODELS_DIR
)
from . import tools as hands

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    Llama = None

try:
    from llama_cpp.llama_chat_format import Llava15ChatHandler, Llava16ChatHandler
    HAS_LLAVA_HANDLER = True
except ImportError:
    HAS_LLAVA_HANDLER = False
    Llava15ChatHandler = None
    Llava16ChatHandler = None

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    from piper.voice import PiperVoice
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False

try:
    import sounddevice as sd
    import soundfile as sf
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# Keywords that suggest the user wants screen / visual awareness
VISION_NEED_KEYWORDS = (
    "screen", "see", "look", "what is on", "what's on", "click", "button",
    "window", "desktop", "cursor", "mouse", "ui", "interface", "display",
    "monitor", "visible", "show me this", "read the", "ocr", "screenshot",
    "where is", "find on screen", "open app", "type in", "fill",
)


def check_model_file(path: str) -> tuple:
    """Validate a GGUF path without loading. Returns (ok: bool, message: str)."""
    if not path or not path.strip():
        return False, "No path provided"
    path = path.strip().strip('"').strip("'")
    if not os.path.exists(path):
        return False, f"File not found: {path}"
    if not path.lower().endswith(".gguf"):
        return False, "File does not end with .gguf"
    try:
        size = os.path.getsize(path)
        if size < 1_000_000:
            return False, f"File too small ({size} bytes) – probably not a real model"
        mb = size / (1024 * 1024)
        return True, f"OK – {os.path.basename(path)} ({mb:.0f} MB)"
    except Exception as e:
        return False, f"Cannot read file: {e}"


class Brain:
    def __init__(self):
        self.cfg = load_config()
        self.llm: Optional[Any] = None
        self.vision_llm: Optional[Any] = None
        self.chat_handler = None
        self.piper = None
        self.tts_engine = None
        self.memory_text = ""
        self.system_prompt = ""
        self.last_vision_summary = ""
        self.text_loaded = False
        self.vision_loaded = False
        # One lock for ALL heavy inference (text OR vision) – they take turns
        self._inference_lock = threading.Lock()
        self._load_lock = threading.Lock()
        self.load_memory()
        self._build_system_prompt()

    # ── Memory ──────────────────────────────────────────────────────────────
    def load_memory(self):
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.memory_text = f.read().strip()
            else:
                self.memory_text = "No long-term memory yet."
        except Exception:
            self.memory_text = ""
        return True, "Memory ready"

    def append_memory(self, text: str):
        try:
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + text.strip() + "\n")
            self.load_memory()
        except Exception as e:
            logger.warning(f"Memory append failed: {e}")

    def _build_system_prompt(self):
        tool_list = "\n".join(
            f"- {t['name']}: {t['description']} | params: {t['parameters']}"
            for t in hands.TOOL_DEFINITIONS
        )
        vision_note = (
            "Vision (Eyes) is AVAILABLE. If you need to know what is on screen, "
            "call the tool <tool>look_screen</tool><args>{}</args> and wait for the result."
            if self.vision_loaded else
            "Vision model is NOT loaded. Do not claim you can see the screen."
        )
        self.system_prompt = f"""You are JARVIS, an advanced personal AI assistant.
You have three components:
1. BRAIN (you) – reasoning and decisions
2. EYES – optional vision model (use only when needed)
3. HANDS – tools you can call to act on the computer

NO-COMMAND mode: interpret natural language and act. Prefer tools over pure talk.

{vision_note}

Available tools:
{tool_list}
- look_screen: Take a screenshot and describe what is on screen (uses Eyes). No parameters.

When you need a tool, output EXACTLY:
<tool>tool_name</tool>
<args>{{"param": "value"}}</args>

Be concise, helpful, slightly witty. Address the user as "sir" when natural.

Long-term memory:
{self.memory_text}

Latest vision summary (may be empty):
{{vision_summary}}
"""

    # ── Unload ──────────────────────────────────────────────────────────────
    def unload_llm(self):
        with self._load_lock:
            if self.llm is not None:
                try:
                    del self.llm
                except Exception:
                    pass
                self.llm = None
                self.text_loaded = False
                import gc
                gc.collect()
                logger.info("Text model unloaded")

    def unload_vision(self):
        with self._load_lock:
            if self.vision_llm is not None:
                try:
                    del self.vision_llm
                except Exception:
                    pass
                self.vision_llm = None
                self.chat_handler = None
                self.vision_loaded = False
                import gc
                gc.collect()
                logger.info("Vision model unloaded")
            self._build_system_prompt()

    def _try_create_llama(self, model_path: str, status_callback=None, **extra):
        """
        Try several Llama() configurations until one works.
        Returns (llama_instance, error_string).
        """
        # Strategies ordered from preferred → most compatible
        strategies = [
            {"n_gpu_layers": -1, "n_ctx": 4096, "n_batch": 512, "verbose": False},
            {"n_gpu_layers": 0,  "n_ctx": 4096, "n_batch": 512, "verbose": False},
            {"n_gpu_layers": -1, "n_ctx": 2048, "n_batch": 256, "verbose": False},
            {"n_gpu_layers": 0,  "n_ctx": 2048, "n_batch": 256, "verbose": False},
            {"n_gpu_layers": 0,  "n_ctx": 1024, "n_batch": 128, "verbose": False},
        ]
        errors = []
        for i, base in enumerate(strategies):
            kwargs = dict(base)
            kwargs.update(extra)
            kwargs["model_path"] = model_path
            label = f"GPU all layers" if kwargs.get("n_gpu_layers") == -1 else "CPU"
            if status_callback:
                status_callback(f"Trying load ({label}, ctx={kwargs['n_ctx']})…")
            try:
                llm = Llama(**kwargs)
                return llm, None
            except TypeError as e:
                # Older llama-cpp may not accept some kwargs – strip and retry once
                errors.append(f"strategy {i+1} TypeError: {e}")
                stripped = {"model_path": model_path, "n_ctx": kwargs.get("n_ctx", 2048),
                            "n_gpu_layers": kwargs.get("n_gpu_layers", 0), "verbose": False}
                if "chat_handler" in extra:
                    stripped["chat_handler"] = extra["chat_handler"]
                try:
                    llm = Llama(**stripped)
                    return llm, None
                except Exception as e2:
                    errors.append(f"strategy {i+1} stripped: {e2}")
            except Exception as e:
                errors.append(f"strategy {i+1} ({label}): {e}")
                logger.warning(f"Llama load attempt failed: {e}")
        return None, " | ".join(errors[-3:])  # last few errors for UI

    # ── Load text (Brain) – alone ───────────────────────────────────────────
    def load_model(self, model_path: str, status_callback: Callable = None) -> bool:
        if not HAS_LLAMA:
            if status_callback:
                status_callback("ERROR: llama-cpp-python is NOT installed. Run: pip install llama-cpp-python")
            return False

        model_path = (model_path or "").strip().strip('"').strip("'")
        # Normalize to absolute path
        try:
            model_path = str(Path(model_path).expanduser().resolve())
        except Exception:
            pass

        ok, msg = check_model_file(model_path)
        if not ok:
            if status_callback:
                status_callback(msg)
            return False

        # Reject obvious vision filenames for the text slot
        lower = model_path.lower()
        if any(k in lower for k in ("mmproj",)):
            if status_callback:
                status_callback("This is an mmproj file – use Vision section for it")
            return False

        with self._load_lock:
            if self.llm is not None:
                try:
                    del self.llm
                except Exception:
                    pass
                self.llm = None
                self.text_loaded = False
                import gc
                gc.collect()
                time.sleep(0.4)

            if status_callback:
                status_callback(f"Loading: {os.path.basename(model_path)}")

            # NOTE: no chat_format= – matches original working code
            llm, err = self._try_create_llama(model_path, status_callback=status_callback)
            if llm is None:
                self.llm = None
                self.text_loaded = False
                # Write full error to log file for debugging
                try:
                    err_path = os.path.join(os.path.dirname(MEMORY_FILE), "jarvis_load_error.txt")
                    with open(err_path, "w", encoding="utf-8") as f:
                        f.write(f"TEXT MODEL LOAD FAILED\nPath: {model_path}\n\n{err}\n")
                except Exception:
                    pass
                if status_callback:
                    short = (err or "unknown error")[:180]
                    status_callback(f"FAILED: {short}")
                logger.error(f"Text load failed: {err}")
                return False

            self.llm = llm
            self.text_loaded = True
            self.cfg["text_model_path"] = model_path
            save_config(self.cfg)
            if status_callback:
                status_callback("Text model (Brain) ready")
            logger.info(f"Text model loaded: {model_path}")
            self._build_system_prompt()
            return True

    # ── Load vision (Eyes) – alone ──────────────────────────────────────────
    def load_vision_model(self, model_path: str, mmproj_path: str = None,
                          status_callback: Callable = None) -> bool:
        if not HAS_LLAMA:
            if status_callback:
                status_callback("ERROR: llama-cpp-python is NOT installed")
            return False

        model_path = (model_path or "").strip().strip('"').strip("'")
        try:
            model_path = str(Path(model_path).expanduser().resolve())
        except Exception:
            pass

        ok, msg = check_model_file(model_path)
        if not ok:
            if status_callback:
                status_callback(msg)
            return False

        if mmproj_path:
            mmproj_path = mmproj_path.strip().strip('"').strip("'")
            try:
                mmproj_path = str(Path(mmproj_path).expanduser().resolve())
            except Exception:
                pass

        with self._load_lock:
            if self.vision_llm is not None:
                try:
                    del self.vision_llm
                except Exception:
                    pass
                self.vision_llm = None
                self.chat_handler = None
                self.vision_loaded = False
                import gc
                gc.collect()
                time.sleep(0.4)

            if status_callback:
                status_callback(f"Loading vision: {os.path.basename(model_path)}")

            chat_handler = None
            if mmproj_path and os.path.exists(mmproj_path) and HAS_LLAVA_HANDLER:
                if status_callback:
                    status_callback("Attaching mmproj / chat handler…")
                for Handler in (Llava15ChatHandler, Llava16ChatHandler):
                    if Handler is None:
                        continue
                    try:
                        chat_handler = Handler(clip_model_path=mmproj_path)
                        logger.info(f"Using {Handler.__name__}")
                        break
                    except Exception as e:
                        logger.warning(f"{Handler} failed: {e}")
                        chat_handler = None

            extra = {}
            if chat_handler:
                extra["chat_handler"] = chat_handler
                extra["logits_all"] = True

            llm, err = self._try_create_llama(
                model_path, status_callback=status_callback, **extra
            )
            if llm is None and chat_handler is not None:
                # Retry without handler – some VL models work differently
                if status_callback:
                    status_callback("Retrying vision without chat handler…")
                llm, err = self._try_create_llama(model_path, status_callback=status_callback)

            if llm is None:
                self.vision_llm = None
                self.vision_loaded = False
                try:
                    err_path = os.path.join(os.path.dirname(MEMORY_FILE), "jarvis_load_error.txt")
                    with open(err_path, "w", encoding="utf-8") as f:
                        f.write(f"VISION MODEL LOAD FAILED\nPath: {model_path}\nmmproj: {mmproj_path}\n\n{err}\n")
                except Exception:
                    pass
                if status_callback:
                    short = (err or "unknown")[:180]
                    status_callback(f"FAILED: {short}")
                logger.error(f"Vision load failed: {err}")
                return False

            self.vision_llm = llm
            self.chat_handler = chat_handler
            self.vision_loaded = True
            self.cfg["vision_model_path"] = model_path
            if mmproj_path:
                self.cfg["vision_mmproj_path"] = mmproj_path
            save_config(self.cfg)
            if status_callback:
                status_callback("Vision model (Eyes) ready")
            logger.info(f"Vision model loaded: {model_path}")
            self._build_system_prompt()
            return True

    def load_piper(self, model_path=None, config_path=None, status_callback=None):
        if not HAS_PIPER:
            if status_callback:
                status_callback("Piper not installed – using system TTS")
            return False
        model_path = model_path or self.cfg.get("piper_model_path")
        config_path = config_path or self.cfg.get("piper_config_path")
        if not model_path or not os.path.exists(model_path):
            if status_callback:
                status_callback("Piper model file missing")
            return False
        try:
            self.piper = PiperVoice.load(model_path, config_path=config_path)
            if status_callback:
                status_callback("Piper TTS ready")
            return True
        except Exception as e:
            logger.warning(f"Piper load failed: {e}")
            if status_callback:
                status_callback(f"Piper failed: {e}")
            return False

    # ── TTS ─────────────────────────────────────────────────────────────────
    def speak(self, text: str, volume: float = 0.9):
        if not text or not text.strip():
            return
        if HAS_PYTTSX3:
            try:
                if self.tts_engine is None:
                    self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty("volume", max(0.0, min(1.0, volume)))
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
                return
            except Exception as e:
                logger.warning(f"TTS failed: {e}")
        print(f"[JARVIS]: {text}")

    # ── Vision one-shot (Eyes) – uses inference lock ────────────────────────
    def analyse_image(self, pil_image, prompt: str = None) -> str:
        if not self.vision_loaded or self.vision_llm is None:
            return "Vision model not loaded."
        if prompt is None:
            prompt = (
                "Describe this computer screen concisely for an AI assistant. "
                "Focus on open windows, visible text, buttons, and actionable UI. Under 100 words."
            )
        # Wait our turn – never run vision while text is generating
        acquired = self._inference_lock.acquire(timeout=120)
        if not acquired:
            return "Vision busy – could not acquire turn."
        try:
            import base64
            from io import BytesIO
            buf = BytesIO()
            pil_image.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            data_uri = f"data:image/png;base64,{b64}"
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            }]
            result = self.vision_llm.create_chat_completion(
                messages=messages, max_tokens=256, temperature=0.2,
            )
            text = result["choices"][0]["message"]["content"]
            return (text or "").strip()
        except Exception as e:
            logger.exception("Vision analysis failed")
            return f"Vision error: {e}"
        finally:
            self._inference_lock.release()

    def update_vision_summary(self, summary: str):
        self.last_vision_summary = summary
        self._build_system_prompt()

    def needs_vision(self, user_message: str) -> bool:
        """Heuristic: does this request likely need the eyes?"""
        if not self.vision_loaded:
            return False
        msg = (user_message or "").lower()
        return any(k in msg for k in VISION_NEED_KEYWORDS)

    def look_screen_once(self) -> str:
        """One-shot screenshot + vision (for tool or agent)."""
        if not self.vision_loaded:
            return "Vision model is not loaded."
        try:
            from PIL import ImageGrab, Image
            img = ImageGrab.grab()
            max_side = 1024
            w, h = img.size
            if max(w, h) > max_side:
                scale = max_side / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            summary = self.analyse_image(img)
            self.update_vision_summary(summary)
            return summary
        except Exception as e:
            return f"Screenshot/vision failed: {e}"

    # ── Agent loop – text only unless vision needed; serialized ─────────────
    def run_agent_loop(self, user_message: str,
                       token_callback: Callable[[str], None] = None,
                       chat_history: List[Dict] = None,
                       max_tool_rounds: int = 6) -> str:
        if not self.text_loaded or self.llm is None:
            return "Text model is not loaded. Use Setup or Settings → Check → Load."

        # Optional: one look before reasoning if the request smells visual
        vision = self.last_vision_summary or ""
        if self.needs_vision(user_message) and self.vision_loaded:
            logger.info("Request needs vision – taking one look (turn-based)")
            vision = self.look_screen_once()
            # small pause so VRAM settles before text model runs
            time.sleep(0.4)

        history = list(chat_history or [])
        system = self.system_prompt.replace("{vision_summary}", vision or "None")

        messages = [{"role": "system", "content": system}]
        for h in history[-12:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_message})

        full_reply = ""
        for round_i in range(max_tool_rounds):
            # Text generation – exclusive turn
            acquired = self._inference_lock.acquire(timeout=180)
            if not acquired:
                return "Brain busy – could not acquire inference turn."
            try:
                stream = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=768,
                    temperature=0.55,
                    top_p=0.9,
                    stream=True,
                )
                chunk_text = ""
                for part in stream:
                    delta = part["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunk_text += delta
                        if token_callback:
                            token_callback(delta)
                full_reply = chunk_text
            except Exception as e:
                logger.exception("Generation failed")
                return f"Generation error: {e}"
            finally:
                self._inference_lock.release()

            tool_calls = re.findall(
                r"<tool>\s*(\w+)\s*</tool>\s*<args>\s*(\{.*?\})\s*</args>",
                full_reply, re.DOTALL | re.IGNORECASE
            )
            if not tool_calls:
                break

            tool_results = []
            for tname, targs_str in tool_calls:
                tname_l = tname.lower().strip()
                try:
                    targs = json.loads(targs_str)
                except Exception:
                    targs = {}
                if tname_l in ("look_screen", "look", "see_screen"):
                    result = self.look_screen_once()
                    time.sleep(0.3)
                else:
                    result = hands.execute_tool(tname_l, targs)
                tool_results.append(f"Tool {tname} → {result}")
                logger.info(f"Tool: {tname} → {str(result)[:100]}")

            messages.append({"role": "assistant", "content": full_reply})
            messages.append({
                "role": "user",
                "content": "Tool results:\n" + "\n".join(tool_results) +
                           "\n\nContinue or give the final answer."
            })
            full_reply = ""

        clean = re.sub(
            r"<tool>.*?</tool>\s*<args>.*?\{.*?\}.*?</args>",
            "", full_reply, flags=re.DOTALL
        ).strip()
        return clean or full_reply.strip()

    def get_filler(self) -> str:
        return random.choice(FILLER_PHRASES)
