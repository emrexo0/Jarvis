"""
JARVIS v2 – Eyes (optional continuous loop)
Only runs when vision model is loaded AND config enables it.
Each look waits for the inference lock so Brain and Eyes never run together.
"""
import threading
import time
from typing import Callable, Optional
from PIL import ImageGrab, Image

from .config import logger, load_config
from .brain import Brain


class VisionLoop:
    def __init__(self, brain: Brain, interval: float = 6.0):
        self.brain = brain
        self.interval = max(3.0, float(interval))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_summary = ""
        self.on_summary: Optional[Callable[[str], None]] = None

    def start(self):
        if self._running:
            return
        cfg = load_config()
        if not cfg.get("vision_enabled", True):
            logger.info("Vision loop disabled in config")
            return
        if not self.brain.vision_loaded or self.brain.vision_llm is None:
            logger.warning("Vision model not loaded – eyes stay closed")
            return
        self.interval = max(3.0, float(cfg.get("vision_interval_sec", 6.0)))
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Eyes opened – interval {self.interval}s (turn-based)")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("Eyes closed")

    def _loop(self):
        # First look after a short delay so UI can settle
        time.sleep(2.0)
        while self._running:
            try:
                if not self.brain.vision_loaded:
                    break
                self._look()
            except Exception as e:
                logger.warning(f"Vision loop error: {e}")
            for _ in range(int(self.interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def _look(self):
        # analyse_image already acquires inference lock
        try:
            img = ImageGrab.grab()
            max_side = 1024
            w, h = img.size
            if max(w, h) > max_side:
                scale = max_side / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            prompt = (
                "You are JARVIS eyes. Describe the screen briefly for the assistant. "
                "Open apps, main text, buttons. Under 80 words."
            )
            summary = self.brain.analyse_image(img, prompt=prompt)
            if summary and not summary.startswith("Vision") and summary != self._last_summary:
                self._last_summary = summary
                self.brain.update_vision_summary(summary)
                if self.on_summary:
                    try:
                        self.on_summary(summary)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Look failed: {e}")

    @property
    def last_summary(self) -> str:
        return self._last_summary
