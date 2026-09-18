"""
JARVIS v2 – Setup screen
Separate Check + Load for text and vision so they never load at the same time.
"""
import os
import threading
import customtkinter as ctk
from tkinter import filedialog

from .config import (
    load_config, save_config, logger,
    DEFAULT_MODEL_PATH, DEFAULT_VISION_PATH, DEFAULT_MMPROJ_PATH, MODELS_DIR
)
from .background import BackgroundAnimator
from .brain import Brain, check_model_file


class SetupScreen(ctk.CTk):
    def __init__(self, on_ready_callback):
        super().__init__()
        self.on_ready = on_ready_callback
        self.title("JARVIS — Setup")
        self.attributes("-fullscreen", True)
        self.configure(fg_color="#000814")

        self.brain = Brain()
        self.cfg = load_config()
        self._loading = False
        from .brain import HAS_LLAMA
        self._has_llama = HAS_LLAMA

        self.bg_canvas = ctk.CTkCanvas(self, bg="#000814", highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg_animator = BackgroundAnimator(self.bg_canvas, star_count=36, dust_count=50)
        self.bg_animator.start()
        self.bg_canvas.bind("<Configure>", lambda e: self.bg_animator._ensure_size())

        self._build_ui()
        self.after(80, self._force_center)
        if not self._has_llama:
            self.after(200, lambda: self.global_status.configure(
                text="CRITICAL: llama-cpp-python not installed — pip install llama-cpp-python",
                text_color="#FF3333"
            ))

    def _force_center(self):
        self.update_idletasks()
        self.main_frame.place(relx=0.5, rely=0.5, anchor="center")

    def _build_ui(self):
        self.main_frame = ctk.CTkFrame(
            self, fg_color="#0a1525", corner_radius=20,
            border_width=1, border_color="#1a4a7a"
        )
        self.main_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self.main_frame, text="J A R V I S",
            font=("Segoe UI", 44, "bold"), text_color="#00E5FF"
        ).pack(pady=(24, 2), padx=50)

        ctk.CTkLabel(
            self.main_frame, text="Load models one at a time — Check path, then Load",
            font=("Segoe UI", 13), text_color="#5a9acc"
        ).pack(pady=(0, 16))

        # ── TEXT MODEL ──
        ctk.CTkLabel(
            self.main_frame, text="TEXT MODEL (Brain)",
            font=("Segoe UI", 13, "bold"), text_color="#7ec8ff"
        ).pack(anchor="w", padx=36)

        row1 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row1.pack(fill="x", padx=36, pady=(4, 2))
        self.text_entry = ctk.CTkEntry(row1, width=400, height=36,
                                       placeholder_text="Path to text .gguf")
        self.text_entry.pack(side="left", padx=(0, 6))
        default_text = self.cfg.get("text_model_path") or DEFAULT_MODEL_PATH
        if default_text:
            self.text_entry.insert(0, default_text)
        ctk.CTkButton(row1, text="BROWSE", width=80, height=36,
                      fg_color="#003566", command=lambda: self._browse(self.text_entry)
                      ).pack(side="left")

        row1b = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row1b.pack(fill="x", padx=36, pady=(2, 4))
        self.text_check_lbl = ctk.CTkLabel(row1b, text="", font=("Segoe UI", 11),
                                           text_color="#88aabb")
        self.text_check_lbl.pack(side="left")
        ctk.CTkButton(row1b, text="CHECK", width=80, height=30,
                      fg_color="#1a3a5a", command=self._check_text
                      ).pack(side="right", padx=4)
        self.text_load_btn = ctk.CTkButton(
            row1b, text="LOAD", width=80, height=30,
            fg_color="#003566", command=self._load_text
        )
        self.text_load_btn.pack(side="right", padx=4)
        self.text_status = ctk.CTkLabel(
            self.main_frame, text="Not loaded", font=("Segoe UI", 11),
            text_color="#FFB703"
        )
        self.text_status.pack(anchor="w", padx=36, pady=(0, 10))

        # ── VISION MODEL ──
        ctk.CTkLabel(
            self.main_frame, text="VISION MODEL (Eyes) — optional",
            font=("Segoe UI", 13, "bold"), text_color="#7ec8ff"
        ).pack(anchor="w", padx=36)

        row2 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row2.pack(fill="x", padx=36, pady=(4, 2))
        self.vis_entry = ctk.CTkEntry(row2, width=400, height=36,
                                      placeholder_text="Path to vision .gguf")
        self.vis_entry.pack(side="left", padx=(0, 6))
        default_vis = self.cfg.get("vision_model_path") or DEFAULT_VISION_PATH
        if default_vis:
            self.vis_entry.insert(0, default_vis)
        ctk.CTkButton(row2, text="BROWSE", width=80, height=36,
                      fg_color="#003566", command=lambda: self._browse(self.vis_entry)
                      ).pack(side="left")

        row2m = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row2m.pack(fill="x", padx=36, pady=(2, 2))
        self.mmproj_entry = ctk.CTkEntry(row2m, width=400, height=34,
                                         placeholder_text="mmproj .gguf (required for most VL models)")
        self.mmproj_entry.pack(side="left", padx=(0, 6))
        default_mm = self.cfg.get("vision_mmproj_path") or DEFAULT_MMPROJ_PATH
        if default_mm:
            self.mmproj_entry.insert(0, default_mm)
        ctk.CTkButton(row2m, text="BROWSE", width=80, height=34,
                      fg_color="#003566", command=lambda: self._browse(self.mmproj_entry)
                      ).pack(side="left")

        row2b = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row2b.pack(fill="x", padx=36, pady=(2, 4))
        self.vis_check_lbl = ctk.CTkLabel(row2b, text="", font=("Segoe UI", 11),
                                          text_color="#88aabb")
        self.vis_check_lbl.pack(side="left")
        ctk.CTkButton(row2b, text="CHECK", width=80, height=30,
                      fg_color="#1a3a5a", command=self._check_vision
                      ).pack(side="right", padx=4)
        self.vis_load_btn = ctk.CTkButton(
            row2b, text="LOAD", width=80, height=30,
            fg_color="#003566", command=self._load_vision
        )
        self.vis_load_btn.pack(side="right", padx=4)
        self.vis_status = ctk.CTkLabel(
            self.main_frame, text="Not loaded (optional)", font=("Segoe UI", 11),
            text_color="#FFB703"
        )
        self.vis_status.pack(anchor="w", padx=36, pady=(0, 12))

        # Status line
        self.global_status = ctk.CTkLabel(
            self.main_frame, text="Check each model, Load one at a time, then Continue",
            font=("Segoe UI", 12), text_color="#88DDFF"
        )
        self.global_status.pack(pady=6)

        btn_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_row.pack(pady=(10, 24))

        ctk.CTkButton(
            btn_row, text="CONTINUE →", width=180, height=44,
            font=("Segoe UI", 14, "bold"), fg_color="#1a5a3a",
            hover_color="#2a7a4a", command=self._continue
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="SKIP ALL", width=120, height=44,
            font=("Segoe UI", 13), fg_color="#001D3D",
            hover_color="#600000", command=self._skip
        ).pack(side="left", padx=8)

    def _browse(self, entry):
        path = filedialog.askopenfilename(
            title="Select GGUF",
            filetypes=[("GGUF files", "*.gguf"), ("All files", "*.*")],
            initialdir=MODELS_DIR if os.path.isdir(MODELS_DIR) else None
        )
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _check_text(self):
        ok, msg = check_model_file(self.text_entry.get())
        self.text_check_lbl.configure(
            text=msg, text_color="#00FF66" if ok else "#FF5555"
        )

    def _check_vision(self):
        ok, msg = check_model_file(self.vis_entry.get())
        mm = self.mmproj_entry.get().strip()
        extra = ""
        if mm:
            mok, mmsg = check_model_file(mm)
            extra = f" | mmproj: {mmsg}"
            if not mok:
                ok = False
        self.vis_check_lbl.configure(
            text=msg + extra, text_color="#00FF66" if ok else "#FF5555"
        )

    def _load_text(self):
        if self._loading:
            self.global_status.configure(text="Already loading something – wait", text_color="#FFB703")
            return
        path = self.text_entry.get().strip()
        ok, msg = check_model_file(path)
        if not ok:
            self.text_status.configure(text=msg, text_color="#FF5555")
            return
        self._loading = True
        self.text_load_btn.configure(state="disabled")
        self.vis_load_btn.configure(state="disabled")
        self.text_status.configure(text="Loading…", text_color="#FFB703")
        self.global_status.configure(text="Loading text model (Brain) only…")

        def worker():
            def _cb(m):
                ml = m.lower()
                if "ready" in ml:
                    col = "#00FF66"
                elif "fail" in ml or "error" in ml:
                    col = "#FF5555"
                else:
                    col = "#FFB703"
                self.after(0, lambda msg=m, c=col: self.text_status.configure(text=msg, text_color=c))
                self.after(0, lambda msg=m: self.global_status.configure(text=msg[:120]))

            success = self.brain.load_model(path, status_callback=_cb)
            def done():
                self._loading = False
                self.text_load_btn.configure(state="normal")
                self.vis_load_btn.configure(state="normal")
                if success:
                    self.text_status.configure(text="LOADED ✓", text_color="#00FF66")
                    self.global_status.configure(text="Text model ready. You can Load vision next or Continue.")
                else:
                    self.text_status.configure(text="FAILED", text_color="#FF5555")
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _load_vision(self):
        if self._loading:
            self.global_status.configure(text="Already loading something – wait", text_color="#FFB703")
            return
        path = self.vis_entry.get().strip()
        mm = self.mmproj_entry.get().strip()
        ok, msg = check_model_file(path)
        if not ok:
            self.vis_status.configure(text=msg, text_color="#FF5555")
            return
        self._loading = True
        self.text_load_btn.configure(state="disabled")
        self.vis_load_btn.configure(state="disabled")
        self.vis_status.configure(text="Loading…", text_color="#FFB703")
        self.global_status.configure(text="Loading vision model (Eyes) only…")

        def worker():
            def _vcb(m):
                ml = m.lower()
                if "ready" in ml:
                    col = "#00FF66"
                elif "fail" in ml or "error" in ml:
                    col = "#FF5555"
                else:
                    col = "#FFB703"
                self.after(0, lambda msg=m, c=col: self.vis_status.configure(text=msg, text_color=c))
                self.after(0, lambda msg=m: self.global_status.configure(text=msg[:120]))

            success = self.brain.load_vision_model(path, mm if mm else None, status_callback=_vcb)
            def done():
                self._loading = False
                self.text_load_btn.configure(state="normal")
                self.vis_load_btn.configure(state="normal")
                if success:
                    self.vis_status.configure(text="LOADED ✓", text_color="#00FF66")
                    self.global_status.configure(text="Vision model ready. Continue when done.")
                else:
                    self.vis_status.configure(text="FAILED – check path / mmproj / VRAM", text_color="#FF5555")
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _continue(self):
        if self._loading:
            self.global_status.configure(text="Wait for current load to finish", text_color="#FFB703")
            return
        if not self.brain.text_loaded:
            self.global_status.configure(
                text="Text model not loaded – Load it or press SKIP ALL",
                text_color="#FF5555"
            )
            return
        self.cfg = self.brain.cfg
        save_config(self.cfg)
        self._finish()

    def _skip(self):
        if self._loading:
            return
        self._finish()

    def _finish(self):
        if self.bg_animator:
            self.bg_animator.stop()
        brain = self.brain
        cfg = self.cfg
        callback = self.on_ready
        self.destroy()
        if callback:
            callback(brain, cfg)
