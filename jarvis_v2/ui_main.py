"""
JARVIS v2 – Main UI
- Click JARVIS core to toggle orbiting menu buttons
- HUDs are draggable / resizable inside the main window
- Extract turns them into real floating windows
- Auto-centers core after fullscreen / resize
"""
import os
import math
import threading
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List

from .config import load_config, save_config, logger
from .background import BackgroundAnimator, BackgroundManager
from .brain import Brain
from .vision import VisionLoop
from .hud import ChatHUD, SettingsHUD, VisionStatusHUD


class JarvisUI(ctk.CTk):
    def __init__(self, brain: Brain = None, config: dict = None):
        super().__init__()
        self.brain = brain or Brain()
        self.cfg = config or load_config()

        self.title("JARVIS System OS")
        self.attributes("-fullscreen", True)
        self.configure(fg_color="#000814")

        # Menu state (orbiting buttons – hidden until JARVIS clicked)
        self.menu_visible = False
        self.menu_buttons: List[ctk.CTkButton] = []
        self.menu_rotation = 0.0
        self.menu_radius = 0.0
        self.menu_radius_target = 0.0

        self.vision_loop: Optional[VisionLoop] = None
        self.animator: Optional[BackgroundAnimator] = None
        self.bg_manager: Optional[BackgroundManager] = None

        self.chat_hud: Optional[ChatHUD] = None
        self.settings_hud: Optional[SettingsHUD] = None
        self.vision_hud: Optional[VisionStatusHUD] = None
        self.open_windows = {}

        self.animation_state = "idle"
        self.pulse_t = 0.0
        self._last_scale = 1.0

        self.core_cx = 0.5
        self.core_cy = 0.55
        self.core_base_r = {"outer": 240, "mid": 190, "inner": 130}

        self._build_main()
        self.after(100, self._force_center)
        self.after(300, self._start_vision_if_ready)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_main(self):
        self.bg_canvas = ctk.CTkCanvas(self, bg="#000814", highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.animator = BackgroundAnimator(self.bg_canvas, star_count=48, dust_count=65)
        self.animator.start()
        self.bg_canvas.bind("<Configure>", self._on_canvas_configure)

        self.bg_manager = BackgroundManager(self, self.bg_canvas, 1280, 800)

        self.time_lbl = ctk.CTkLabel(
            self, text="00:00", font=("Segoe UI", 36, "bold"), text_color="#00E5FF"
        )
        self.time_lbl.place(relx=0.03, rely=0.03, anchor="nw")
        self._tick_clock()

        self.slogan_lbl = ctk.CTkLabel(
            self, text="JUST A RATHER VERY INTELLIGENT SYSTEM",
            font=("Segoe UI", 16), text_color="#00A8C8"
        )
        self.slogan_lbl.place(relx=0.5, rely=0.12, anchor="center")

        self.outer = self.bg_canvas.create_oval(0, 0, 0, 0, outline="#001D3D", width=2)
        self.mid   = self.bg_canvas.create_oval(0, 0, 0, 0, outline="#003566", width=2)
        self.inner = self.bg_canvas.create_oval(0, 0, 0, 0, outline="#00E5FF", width=3)
        self.core_btn = self.bg_canvas.create_text(
            0, 0, text="JARVIS", fill="#00E5FF",
            font=("Segoe UI", 42, "bold")
        )
        self.bg_canvas.tag_bind(self.core_btn, "<Enter>",
                                lambda e: self.bg_canvas.itemconfigure(self.core_btn, fill="white"))
        self.bg_canvas.tag_bind(self.core_btn, "<Leave>",
                                lambda e: self.bg_canvas.itemconfigure(self.core_btn, fill="#00E5FF"))
        self.bg_canvas.tag_bind(self.core_btn, "<Button-1>", lambda e: self.toggle_menu())

        self.menu_items = [
            ("CHAT",     self._toggle_chat),
            ("SETTINGS", self._toggle_settings),
            ("EYES",     self._toggle_vision_hud),
            ("MEMORY",   self._show_memory),
            ("TURN OFF", self._on_close),
        ]

        self.status_var = ctk.StringVar(value="Systems online")
        self.status_label = ctk.CTkLabel(
            self, textvariable=self.status_var,
            font=("Segoe UI", 11), text_color="#4a7a9a"
        )
        self.status_label.place(relx=0.5, rely=0.97, anchor="center")

        self._start_core_animation()

    def _tick_clock(self):
        import datetime
        if self.winfo_exists():
            self.time_lbl.configure(text=datetime.datetime.now().strftime("%H:%M"))
            self.after(1000, self._tick_clock)

    def _force_center(self):
        self.update_idletasks()
        self._position_core_rings()
        try:
            self.slogan_lbl.place(relx=0.5, rely=0.12, anchor="center")
        except Exception:
            pass

    def _on_canvas_configure(self, event=None):
        if self.animator:
            self.animator._ensure_size()
        self._position_core_rings()
        if self.bg_manager:
            try:
                self.bg_manager.resize(self.winfo_width(), self.winfo_height())
            except Exception:
                pass

    def _position_core_rings(self):
        try:
            w = max(self.winfo_width(), 800)
            h = max(self.winfo_height(), 600)
            cx = w * self.core_cx
            cy = h * self.core_cy
            scale = getattr(self, "_last_scale", 1.0)
            for obj, key in [(self.outer, "outer"), (self.mid, "mid"), (self.inner, "inner")]:
                r = self.core_base_r[key] * scale
                self.bg_canvas.coords(obj, cx - r, cy - r, cx + r, cy + r)
            self.bg_canvas.coords(self.core_btn, cx, cy)
            self.bg_canvas.tag_raise(self.outer)
            self.bg_canvas.tag_raise(self.mid)
            self.bg_canvas.tag_raise(self.inner)
            self.bg_canvas.tag_raise(self.core_btn)
        except Exception:
            pass

    def toggle_menu(self):
        self.menu_visible = not self.menu_visible
        if self.menu_visible:
            if not self.menu_buttons:
                self._create_menu_buttons()
            self.menu_radius_target = 250.0
        else:
            self.menu_radius_target = 0.0

    def _create_menu_buttons(self):
        for b in self.menu_buttons:
            try:
                b.destroy()
            except Exception:
                pass
        self.menu_buttons = []
        for text, cmd in self.menu_items:
            btn = ctk.CTkButton(
                self, text=text, width=150, height=42,
                font=("Segoe UI", 14, "bold"),
                fg_color="#001D3D", text_color="#A5F2FF",
                border_width=2, border_color="#00E5FF",
                hover_color="#003566", corner_radius=12,
                command=cmd
            )
            btn.bind("<Enter>", lambda e, b=btn: b.configure(
                border_color="#80FFFF", fg_color="#002B4F"))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(
                border_color="#00E5FF", fg_color="#001D3D"))
            self.menu_buttons.append(btn)
            btn.place_forget()

    def _position_menu(self):
        if not self.menu_buttons:
            return
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        cx, cy = w * self.core_cx, h * self.core_cy
        r = self.menu_radius
        n = len(self.menu_buttons)
        for i, btn in enumerate(self.menu_buttons):
            ang = (i * (2 * math.pi / n)) + self.menu_rotation
            x = cx + r * math.cos(ang)
            y = cy + r * math.sin(ang)
            if r > 12:
                btn.place(x=x, y=y, anchor="center")
            else:
                btn.place_forget()

    def _start_core_animation(self):
        def loop():
            if not self.winfo_exists():
                return
            self.pulse_t += 0.02
            base = 1.0 + 0.035 * math.sin(self.pulse_t)
            if self.animation_state == "thinking":
                scale = 1.0 + 0.08 * math.sin(self.pulse_t * 2.4)
            else:
                scale = base
            self._last_scale = scale
            self._position_core_rings()

            self.menu_rotation += 0.0018
            self.menu_radius = self.menu_radius * 0.90 + self.menu_radius_target * 0.10
            self._position_menu()
            if self.menu_radius_target == 0 and self.menu_radius < 12:
                for b in self.menu_buttons:
                    b.place_forget()

            br = int(100 + 80 * math.sin(self.pulse_t * 0.5))
            try:
                self.slogan_lbl.configure(text_color=f"#00{br:02x}{min(br+40,255):02x}")
            except Exception:
                pass

            self.after(33, loop)
        loop()

    def _start_vision_if_ready(self):
        if getattr(self.brain, "vision_loaded", False) and self.brain.vision_llm is not None and self.cfg.get("vision_enabled", True):
            self.vision_loop = VisionLoop(
                self.brain, interval=self.cfg.get("vision_interval_sec", 4.0)
            )
            self.vision_loop.on_summary = self._on_vision_summary
            self.vision_loop.start()
            self.status_var.set("Eyes online – continuous vision active")
        else:
            self.status_var.set("Systems online (vision off or not loaded)")

    def _on_vision_summary(self, summary: str):
        if self.vision_hud and self.vision_hud.winfo_exists():
            try:
                self.after(0, lambda: self.vision_hud.update_summary(summary))
            except Exception:
                pass

    def _place_hud(self, hud, offset_x=0, offset_y=0):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        hw = hud.winfo_reqwidth() or 440
        hh = hud.winfo_reqheight() or 500
        x = (w - hw) // 2 + offset_x
        y = (h - hh) // 2 + offset_y
        hud.place(x=max(20, x), y=max(40, y))

    def _toggle_chat(self):
        if self.chat_hud and self.chat_hud.winfo_exists():
            self.chat_hud.destroy()
            self.chat_hud = None
            return
        self.chat_hud = ChatHUD(
            self, self.brain,
            on_close=lambda: setattr(self, "chat_hud", None),
            on_extract=self._extract_chat,
            send_callback=self._handle_user_message
        )
        self._place_hud(self.chat_hud, offset_x=-30, offset_y=-20)

    def _toggle_settings(self):
        if self.settings_hud and self.settings_hud.winfo_exists():
            self.settings_hud.destroy()
            self.settings_hud = None
            return
        self.settings_hud = SettingsHUD(
            self, self.brain, self.cfg,
            on_close=lambda: setattr(self, "settings_hud", None),
            on_extract=self._extract_settings,
            on_save=self._apply_settings
        )
        self._place_hud(self.settings_hud, offset_x=40, offset_y=10)

    def _toggle_vision_hud(self):
        if self.vision_hud and self.vision_hud.winfo_exists():
            self.vision_hud.destroy()
            self.vision_hud = None
            return
        self.vision_hud = VisionStatusHUD(
            self, on_close=lambda: setattr(self, "vision_hud", None)
        )
        if self.vision_loop and self.vision_loop.last_summary:
            self.vision_hud.update_summary(self.vision_loop.last_summary)
        self._place_hud(self.vision_hud, offset_x=-60, offset_y=60)

    def _extract_chat(self):
        win = ctk.CTkToplevel(self)
        win.title("JARVIS — Chat")
        win.geometry("520x640")
        win.configure(fg_color="#0c1a2e")
        win.attributes("-topmost", True)
        chat = ChatHUD(
            win, self.brain,
            on_close=win.destroy,
            on_extract=None,
            send_callback=self._handle_user_message
        )
        chat.pack(fill="both", expand=True, padx=4, pady=4)
        self.chat_hud = None
        self.open_windows["chat"] = win

    def _extract_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("JARVIS — Settings")
        win.geometry("480x600")
        win.configure(fg_color="#0c1a2e")
        win.attributes("-topmost", True)
        settings = SettingsHUD(
            win, self.brain, self.cfg,
            on_close=win.destroy,
            on_extract=None,
            on_save=self._apply_settings
        )
        settings.pack(fill="both", expand=True, padx=4, pady=4)
        self.settings_hud = None
        self.open_windows["settings"] = win

    def _apply_settings(self, new_cfg):
        self.cfg = new_cfg
        save_config(self.cfg)
        self.status_var.set("Settings saved")
        if self.vision_loop:
            self.vision_loop.stop()
            self.vision_loop = None
        self.after(200, self._start_vision_if_ready)

    def _show_memory(self):
        top = ctk.CTkToplevel(self)
        top.title("Long-term Memory")
        top.geometry("520x420")
        top.configure(fg_color="#000814")
        txt = ctk.CTkTextbox(top, font=("Consolas", 12))
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        txt.insert("1.0", self.brain.memory_text or "(empty)")
        txt.configure(state="disabled")

    def _handle_user_message(self, message: str):
        if not self.chat_hud or not self.chat_hud.winfo_exists():
            return
        hud = self.chat_hud
        hud.model_busy = True
        hud.set_status("busy")
        self.animation_state = "thinking"
        jarvis_lbl = hud.add_jarvis_text("● ● ●")

        def worker():
            def token_cb(tok):
                self.after(0, lambda t=tok: hud.stream_token(jarvis_lbl, t))

            try:
                prev = [{"role": "user" if m["sender"] == "user" else "assistant",
                         "content": m["text"]} for m in hud.chat_history[:-1]]
                reply = self.brain.run_agent_loop(
                    message, token_callback=token_cb, chat_history=prev
                )
                self.after(0, lambda: jarvis_lbl.configure(text=reply or jarvis_lbl.cget("text")))
                hud.chat_history.append({"sender": "jarvis", "text": reply})
                try:
                    self.brain.speak(reply, volume=self.cfg.get("speech_volume", 0.85))
                except Exception:
                    pass
            except Exception as e:
                self.after(0, lambda: jarvis_lbl.configure(text=f"Error: {e}"))
                self.after(0, lambda: hud.set_status("error"))
            finally:
                hud.model_busy = False
                self.animation_state = "idle"
                self.after(0, lambda: hud.set_status("ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        if self.vision_loop:
            self.vision_loop.stop()
        if self.animator:
            self.animator.stop()
        if self.bg_manager:
            self.bg_manager.stop()
        self.brain.unload_llm()
        self.brain.unload_vision()
        self.destroy()
