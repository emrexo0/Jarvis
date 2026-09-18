"""
JARVIS v2 – Cinematic loading screen
Each visual phase runs real lightweight init so the animation is not skipped.
Heavy GGUF loads stay on the Setup screen (Check / Load).
"""
import math
import os
import threading
import customtkinter as ctk

from .config import logger, load_config, MEMORY_FILE, MODELS_DIR, CACHE_DIR, TEMP_DIR, CHATS_DIR


class IntroSequence(ctk.CTkToplevel):
    """
    Phases with real work:
      0 – single circle + create dirs / config
      1 – rings expand + load memory file
      2 – JARVIS text + verify optional deps
      3 – orbiting labels + path scan
      4 – fade + hand off to Setup
    """

    def __init__(self, master, on_finished_callback):
        super().__init__(master)
        self.on_finished = on_finished_callback
        self.attributes("-fullscreen", True)
        self.configure(fg_color="#000000")
        self.overrideredirect(True)
        self.lift()
        self.attributes("-topmost", True)

        self.w = self.winfo_screenwidth()
        self.h = self.winfo_screenheight()
        self.cx = self.w // 2
        self.cy = self.h // 2

        self.canvas = ctk.CTkCanvas(
            self, width=self.w, height=self.h,
            bg="#000000", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.status_id = self.canvas.create_text(
            self.cx, self.h - 60,
            text="Initializing…", fill="#3a6a9a",
            font=("Segoe UI", 14), anchor="center"
        )

        self.phase = 0
        self.t = 0.0
        self.circle_ids = []
        self.text_id = None
        self.button_ids = []
        self.orbit_angles = []
        self._running = True
        self._phase_work_done = {0: False, 1: False, 2: False, 3: False}

        self.after(80, self._start_phase_0)

    def _set_status(self, text: str):
        try:
            self.canvas.itemconfigure(self.status_id, text=text)
        except Exception:
            pass

    # ── Phase 0 ─────────────────────────────────────────────────────────────
    def _start_phase_0(self):
        self._set_status("Creating system folders…")
        threading.Thread(target=self._work_phase_0, daemon=True).start()
        r = 40
        cid = self.canvas.create_oval(
            self.cx - r, self.cy - r, self.cx + r, self.cy + r,
            outline="#1a4a7a", width=2, fill=""
        )
        self.circle_ids.append(cid)
        self._animate_phase_0()

    def _work_phase_0(self):
        for d in (MODELS_DIR, CACHE_DIR, TEMP_DIR, CHATS_DIR):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
        load_config()
        self._phase_work_done[0] = True

    def _animate_phase_0(self):
        if not self._running:
            return
        self.t += 0.04
        r = 40 + 8 * math.sin(self.t * 3)
        alpha = min(1.0, self.t / 1.5)
        col = self._lerp_color("#000000", "#3a9eff", alpha)
        try:
            self.canvas.coords(
                self.circle_ids[0],
                self.cx - r, self.cy - r, self.cx + r, self.cy + r
            )
            self.canvas.itemconfigure(self.circle_ids[0], outline=col)
        except Exception:
            pass
        if self.t < 2.0 or not self._phase_work_done[0]:
            self.after(40, self._animate_phase_0)
        else:
            self.t = 0.0
            self._start_phase_1()

    # ── Phase 1 ─────────────────────────────────────────────────────────────
    def _start_phase_1(self):
        self._set_status("Loading long-term memory…")
        threading.Thread(target=self._work_phase_1, daemon=True).start()
        for i in range(1, 6):
            r = 55 + i * 38
            cid = self.canvas.create_oval(
                self.cx - r, self.cy - r, self.cx + r, self.cy + r,
                outline="#0a2038", width=1, fill=""
            )
            self.circle_ids.append(cid)
        self.canvas.tag_raise(self.circle_ids[0])
        self._animate_phase_1()

    def _work_phase_1(self):
        try:
            if not os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    f.write("System Name: JARVIS\nVersion: 2.0\n")
            else:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    f.read()
        except Exception:
            pass
        import time
        time.sleep(0.4)
        self._phase_work_done[1] = True

    def _animate_phase_1(self):
        if not self._running:
            return
        self.t += 0.035
        progress = min(1.0, self.t / 2.5)
        for i, cid in enumerate(self.circle_ids):
            base_r = 40 + i * 38
            r = base_r * (0.6 + 0.4 * progress) + 4 * math.sin(self.t * 2 + i)
            col = self._lerp_color("#050d18", "#2a7fd4", progress * (0.4 + 0.6 * (i / 6)))
            try:
                self.canvas.coords(cid, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
                self.canvas.itemconfigure(cid, outline=col, width=1 + (1 if i == 0 else 0))
            except Exception:
                pass
        if progress < 1.0 or not self._phase_work_done[1]:
            self.after(40, self._animate_phase_1)
        else:
            self.t = 0.0
            self._start_phase_2()

    # ── Phase 2 ─────────────────────────────────────────────────────────────
    def _start_phase_2(self):
        self._set_status("Checking runtime libraries…")
        threading.Thread(target=self._work_phase_2, daemon=True).start()
        self.text_id = self.canvas.create_text(
            self.cx, self.cy, text="J A R V I S",
            font=("Segoe UI", 42, "bold"), fill="#000000", anchor="center"
        )
        self._animate_phase_2()

    def _work_phase_2(self):
        checks = []
        try:
            import customtkinter  # noqa
            checks.append("UI")
        except Exception:
            pass
        try:
            from llama_cpp import Llama  # noqa
            checks.append("llama.cpp")
        except Exception:
            pass
        try:
            from PIL import Image  # noqa
            checks.append("PIL")
        except Exception:
            pass
        self._set_status("Libraries: " + (", ".join(checks) if checks else "limited"))
        import time
        time.sleep(0.5)
        self._phase_work_done[2] = True

    def _animate_phase_2(self):
        if not self._running:
            return
        self.t += 0.04
        progress = min(1.0, self.t / 1.5)
        col = self._lerp_color("#000000", "#a0d4ff", progress)
        try:
            self.canvas.itemconfigure(self.text_id, fill=col)
        except Exception:
            pass
        if progress < 1.0 or not self._phase_work_done[2]:
            self.after(40, self._animate_phase_2)
        else:
            self.t = 0.0
            self._start_phase_3()

    # ── Phase 3 ─────────────────────────────────────────────────────────────
    def _start_phase_3(self):
        self._set_status("Scanning model directory…")
        threading.Thread(target=self._work_phase_3, daemon=True).start()
        labels = ["BRAIN", "EYES", "HANDS", "MEMORY", "CORE"]
        self.button_ids = []
        self.orbit_angles = []
        for i, lab in enumerate(labels):
            angle = (i / len(labels)) * 2 * math.pi
            start_r = max(self.w, self.h) * 0.7
            x = self.cx + start_r * math.cos(angle)
            y = self.cy + start_r * math.sin(angle)
            tid = self.canvas.create_text(
                x, y, text=lab, font=("Segoe UI", 13, "bold"),
                fill="#1a3a5a", anchor="center"
            )
            self.button_ids.append(tid)
            self.orbit_angles.append(angle)
        self._animate_phase_3()

    def _work_phase_3(self):
        n = 0
        try:
            if os.path.isdir(MODELS_DIR):
                for root, dirs, files in os.walk(MODELS_DIR):
                    for f in files:
                        if f.lower().endswith(".gguf"):
                            n += 1
        except Exception:
            pass
        self._set_status(f"Found {n} GGUF file(s) in models/")
        import time
        time.sleep(0.6)
        self._phase_work_done[3] = True

    def _animate_phase_3(self):
        if not self._running:
            return
        self.t += 0.035
        if self.t < 2.4:
            progress = self.t / 2.4
            target_r = 160 + 30 * math.sin(self.t * 4)
            for i, tid in enumerate(self.button_ids):
                ang = self.orbit_angles[i] + self.t * 1.8
                r = (1.0 - progress) * max(self.w, self.h) * 0.65 + progress * target_r
                x = self.cx + r * math.cos(ang)
                y = self.cy + r * math.sin(ang)
                col = self._lerp_color("#0a1525", "#4aa0ff", progress)
                try:
                    self.canvas.coords(tid, x, y)
                    self.canvas.itemconfigure(tid, fill=col)
                except Exception:
                    pass
            self.after(35, self._animate_phase_3)
        elif self.t < 3.6 or not self._phase_work_done[3]:
            for i, tid in enumerate(self.button_ids):
                ang = self.orbit_angles[i]
                r = 175
                x = self.cx + r * math.cos(ang)
                y = self.cy + r * math.sin(ang)
                try:
                    self.canvas.coords(tid, x, y)
                    self.canvas.itemconfigure(tid, fill="#7ec8ff")
                except Exception:
                    pass
            self.after(35, self._animate_phase_3)
        else:
            self.t = 0.0
            self._start_phase_4()

    # ── Phase 4 ─────────────────────────────────────────────────────────────
    def _start_phase_4(self):
        self._set_status("Handing off to model setup…")
        self._animate_phase_4()

    def _animate_phase_4(self):
        if not self._running:
            return
        self.t += 0.04
        progress = min(1.0, self.t / 1.2)
        for cid in self.circle_ids:
            try:
                self.canvas.itemconfigure(
                    cid, outline=self._lerp_color("#2a7fd4", "#000000", progress)
                )
            except Exception:
                pass
        if self.text_id:
            try:
                self.canvas.itemconfigure(
                    self.text_id, fill=self._lerp_color("#a0d4ff", "#000000", progress)
                )
            except Exception:
                pass
        for tid in self.button_ids:
            try:
                self.canvas.itemconfigure(
                    tid, fill=self._lerp_color("#7ec8ff", "#000000", progress)
                )
            except Exception:
                pass
        if progress < 1.0:
            self.after(40, self._animate_phase_4)
        else:
            self._finish()

    def _finish(self):
        self._running = False
        try:
            self.destroy()
        except Exception:
            pass
        if self.on_finished:
            self.on_finished()

    def _lerp_color(self, c1: str, c2: str, t: float) -> str:
        t = max(0.0, min(1.0, t))
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        r1, g1, b1 = hex_to_rgb(c1)
        r2, g2, b2 = hex_to_rgb(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"
