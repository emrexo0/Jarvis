"""
JARVIS v2 – Futuristic HUD panels
- Draggable by header
- Resizable from bottom-right corner
- Extract button turns them into real movable Toplevel windows
- Chat: user bubbles, Jarvis plain text, status dot, streaming, save/load
"""
import os
import datetime
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from .config import CHATS_DIR, logger


class HUDPanel(ctk.CTkFrame):
    """Semi-transparent panel that lives inside the main UI.
    Drag by header, resize from bottom-right grip, extract to real window.
    """

    MIN_W, MIN_H = 280, 200

    def __init__(self, master, title: str, width=440, height=520,
                 on_close: Callable = None, on_extract: Callable = None):
        super().__init__(
            master,
            width=width, height=height,
            corner_radius=14,
            fg_color=("#0c1a2e", "#0c1a2e"),
            border_width=1,
            border_color="#2a5a8a",
        )
        self.title_text = title
        self.on_close_cb = on_close
        self.on_extract_cb = on_extract
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._drag_data = {"x": 0, "y": 0}
        self._resize_data = {"x": 0, "y": 0, "w": width, "h": height}
        self._resizing = False

        # Header
        self.header = ctk.CTkFrame(self, height=36, fg_color="#12253d", corner_radius=0)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        ctk.CTkLabel(
            self.header, text=title.upper(),
            font=("Segoe UI", 13, "bold"), text_color="#7ec8ff"
        ).pack(side="left", padx=14, pady=6)

        if on_extract:
            ctk.CTkButton(
                self.header, text="⧉", width=28, height=24,
                fg_color="transparent", hover_color="#1a3a5a",
                text_color="#5a9acc", font=("Segoe UI", 14),
                command=self._do_extract
            ).pack(side="right", padx=2, pady=4)

        ctk.CTkButton(
            self.header, text="✕", width=28, height=24,
            fg_color="transparent", hover_color="#5a2030",
            text_color="#cc7a8a", font=("Segoe UI", 13),
            command=self._do_close
        ).pack(side="right", padx=4, pady=4)

        self.header.bind("<ButtonPress-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._do_drag)
        for child in self.header.winfo_children():
            child.bind("<ButtonPress-1>", self._start_drag)
            child.bind("<B1-Motion>", self._do_drag)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.grip = ctk.CTkLabel(
            self, text="◢", font=("Segoe UI", 11),
            text_color="#3a6a9a", width=18, height=18
        )
        self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-2)
        self.grip.bind("<ButtonPress-1>", self._start_resize)
        self.grip.bind("<B1-Motion>", self._do_resize)
        self.grip.bind("<ButtonRelease-1>", self._end_resize)

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _do_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root
        try:
            x = self.winfo_x() + dx
            y = self.winfo_y() + dy
            self.place(x=x, y=y)
        except Exception:
            pass

    def _start_resize(self, event):
        self._resizing = True
        self._resize_data = {
            "x": event.x_root, "y": event.y_root,
            "w": self.winfo_width(), "h": self.winfo_height()
        }

    def _do_resize(self, event):
        if not self._resizing:
            return
        dx = event.x_root - self._resize_data["x"]
        dy = event.y_root - self._resize_data["y"]
        new_w = max(self.MIN_W, self._resize_data["w"] + dx)
        new_h = max(self.MIN_H, self._resize_data["h"] + dy)
        self.configure(width=new_w, height=new_h)

    def _end_resize(self, event):
        self._resizing = False

    def _do_close(self):
        if self.on_close_cb:
            self.on_close_cb()
        self.destroy()

    def _do_extract(self):
        if self.on_extract_cb:
            self.on_extract_cb()
        self.destroy()


class ChatHUD(HUDPanel):
    def __init__(self, master, brain, on_close=None, on_extract=None,
                 send_callback: Callable = None):
        super().__init__(master, "Chat", width=480, height=580,
                         on_close=on_close, on_extract=on_extract)
        self.brain = brain
        self.send_callback = send_callback
        self.chat_history = []
        self.chat_filename = None
        self.model_busy = False

        top = ctk.CTkFrame(self.content, fg_color="transparent", height=32)
        top.pack(fill="x", pady=(0, 6))
        top.pack_propagate(False)

        self.status_dot = ctk.CTkLabel(
            top, text="●", font=("Segoe UI", 16),
            text_color="#00FF66", width=24
        )
        self.status_dot.pack(side="left", padx=(4, 2))
        self.status_lbl = ctk.CTkLabel(
            top, text="READY", font=("Segoe UI", 11),
            text_color="#00FF66"
        )
        self.status_lbl.pack(side="left")

        ctk.CTkButton(
            top, text="SAVE", width=70, height=26,
            fg_color="#003566", font=("Segoe UI", 11),
            command=self._save_chat
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            top, text="LOAD", width=70, height=26,
            fg_color="#003566", font=("Segoe UI", 11),
            command=self._load_chat_dialog
        ).pack(side="right", padx=2)

        self.chat_area = ctk.CTkScrollableFrame(
            self.content, fg_color="#08101c",
            scrollbar_button_color="#1a3a5a"
        )
        self.chat_area.pack(fill="both", expand=True, pady=(0, 8))

        inp = ctk.CTkFrame(self.content, fg_color="transparent")
        inp.pack(fill="x")

        self.entry = ctk.CTkEntry(
            inp, placeholder_text="Speak freely… (no commands needed)",
            font=("Segoe UI", 13), height=38,
            fg_color="#0e1c30", border_color="#2a5a8a"
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self._send())

        ctk.CTkButton(
            inp, text="SEND", width=70, height=38,
            fg_color="#1a4a7a", hover_color="#2a6aaa",
            font=("Segoe UI", 12, "bold"),
            command=self._send
        ).pack(side="right")

    def set_status(self, state: str):
        colors = {
            "ready": ("#00FF66", "READY"),
            "busy":  ("#FFB703", "PROCESSING…"),
            "error": ("#FF3333", "ERROR"),
        }
        col, txt = colors.get(state, colors["ready"])
        try:
            self.status_dot.configure(text_color=col)
            self.status_lbl.configure(text=txt, text_color=col)
        except Exception:
            pass

    def add_user_bubble(self, text: str):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(fill="x", pady=4, padx=4)
        bubble = ctk.CTkLabel(
            frame, text=text,
            fg_color="#003566", text_color="#FFFFFF",
            corner_radius=14, padx=14, pady=8,
            wraplength=340, justify="left",
            font=("Segoe UI", 13)
        )
        bubble.pack(anchor="e")
        self._scroll_bottom()

    def add_jarvis_text(self, text: str = ""):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(fill="x", pady=4, padx=4)
        lbl = ctk.CTkLabel(
            frame, text=text or "● ● ●",
            fg_color="transparent", text_color="#00E5FF",
            wraplength=380, justify="left",
            font=("Segoe UI", 13), anchor="w"
        )
        lbl.pack(anchor="w", fill="x")
        self._scroll_bottom()
        return lbl

    def stream_token(self, label, token: str):
        try:
            cur = label.cget("text")
            if cur == "● ● ●":
                label.configure(text=token)
            else:
                label.configure(text=cur + token)
            self._scroll_bottom()
        except Exception:
            pass

    def _scroll_bottom(self):
        try:
            self.chat_area._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _send(self):
        msg = self.entry.get().strip()
        if not msg or self.model_busy:
            return
        self.entry.delete(0, "end")
        self.add_user_bubble(msg)
        self.chat_history.append({"sender": "user", "text": msg})
        if self.send_callback:
            self.send_callback(msg)

    def _save_chat(self):
        if not self.chat_history:
            return
        if self.chat_filename:
            path = os.path.join(CHATS_DIR, self.chat_filename)
        else:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.chat_filename = f"chat_{ts}.txt"
            path = os.path.join(CHATS_DIR, self.chat_filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                for msg in self.chat_history:
                    prefix = "USER" if msg["sender"] == "user" else "JARVIS"
                    f.write(f"{prefix}: {msg['text']}\n\n")
            self.status_lbl.configure(text="SAVED", text_color="#00FF41")
            self.after(2000, lambda: self.set_status("ready"))
        except Exception as e:
            logger.warning(f"Save chat failed: {e}")

    def _load_chat_dialog(self):
        files = [f for f in os.listdir(CHATS_DIR)
                 if f.startswith("chat_") and f.endswith(".txt")]
        if not files:
            messagebox.showinfo("History", "No saved chats yet.")
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Saved Conversations")
        dlg.geometry("420x400")
        dlg.configure(fg_color="#000814")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="Saved Chats", font=("Segoe UI", 18, "bold"),
                     text_color="#00E5FF").pack(pady=12)
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for fname in sorted(files, reverse=True):
            display = fname.replace("chat_", "").replace(".txt", "").replace("_", " ")
            ctk.CTkButton(
                scroll, text=display, width=360, height=40,
                fg_color="#001D3D", hover_color="#003566", anchor="w",
                command=lambda f=fname, d=dlg: self._load_chat(f, d)
            ).pack(pady=3)

    def _load_chat(self, filename, dialog):
        path = os.path.join(CHATS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for w in self.chat_area.winfo_children():
                w.destroy()
            self.chat_history = []
            self.chat_filename = filename
            blocks = content.strip().split("\n\n")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                if block.startswith("USER: "):
                    text = block[6:].strip()
                    self.add_user_bubble(text)
                    self.chat_history.append({"sender": "user", "text": text})
                elif block.startswith("JARVIS: "):
                    text = block[8:].strip()
                    self.add_jarvis_text(text)
                    self.chat_history.append({"sender": "jarvis", "text": text})
            dialog.destroy()
        except Exception as e:
            logger.warning(f"Load chat failed: {e}")



class SettingsHUD(HUDPanel):
    def __init__(self, master, brain, config, on_close=None, on_extract=None,
                 on_save: Callable = None):
        super().__init__(master, "Settings", width=480, height=600,
                         on_close=on_close, on_extract=on_extract)
        self.brain = brain
        self.cfg = config
        self.on_save = on_save
        self._loading = False

        scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        def section(title):
            ctk.CTkLabel(scroll, text=title, font=("Segoe UI", 12, "bold"),
                         text_color="#5a9acc").pack(anchor="w", pady=(12, 4))

        from .brain import check_model_file
        self._check_model_file = check_model_file

        section("TEXT MODEL (Brain)")
        self.text_path = ctk.CTkEntry(scroll, height=32)
        self.text_path.insert(0, self.cfg.get("text_model_path", ""))
        self.text_path.pack(fill="x", pady=2)
        row_t = ctk.CTkFrame(scroll, fg_color="transparent")
        row_t.pack(fill="x", pady=2)
        ctk.CTkButton(row_t, text="Browse", width=70, height=28,
                      command=lambda: self._browse(self.text_path)).pack(side="left", padx=2)
        ctk.CTkButton(row_t, text="CHECK", width=70, height=28, fg_color="#1a3a5a",
                      command=self._check_text).pack(side="left", padx=2)
        ctk.CTkButton(row_t, text="LOAD", width=70, height=28, fg_color="#003566",
                      command=self._load_text).pack(side="left", padx=2)
        self.text_status = ctk.CTkLabel(scroll, text="Use CHECK then LOAD", font=("Segoe UI", 11),
                                        text_color="#88aabb")
        self.text_status.pack(anchor="w")

        section("VISION MODEL (Eyes)")
        self.vis_path = ctk.CTkEntry(scroll, height=32)
        self.vis_path.insert(0, self.cfg.get("vision_model_path", ""))
        self.vis_path.pack(fill="x", pady=2)
        ctk.CTkLabel(scroll, text="mmproj", text_color="#6a8aaa").pack(anchor="w")
        self.mmproj_path = ctk.CTkEntry(scroll, height=32)
        self.mmproj_path.insert(0, self.cfg.get("vision_mmproj_path", ""))
        self.mmproj_path.pack(fill="x", pady=2)
        row_v = ctk.CTkFrame(scroll, fg_color="transparent")
        row_v.pack(fill="x", pady=2)
        ctk.CTkButton(row_v, text="Browse", width=70, height=28,
                      command=lambda: self._browse(self.vis_path)).pack(side="left", padx=2)
        ctk.CTkButton(row_v, text="CHECK", width=70, height=28, fg_color="#1a3a5a",
                      command=self._check_vision).pack(side="left", padx=2)
        ctk.CTkButton(row_v, text="LOAD", width=70, height=28, fg_color="#003566",
                      command=self._load_vision).pack(side="left", padx=2)
        self.vis_status = ctk.CTkLabel(scroll, text="Optional – CHECK then LOAD", font=("Segoe UI", 11),
                                       text_color="#88aabb")
        self.vis_status.pack(anchor="w")

        section("VISION LOOP")
        self.vision_enabled = ctk.CTkSwitch(scroll, text="Enable continuous screen watching")
        if self.cfg.get("vision_enabled", True):
            self.vision_enabled.select()
        self.vision_enabled.pack(anchor="w", pady=4)
        self.interval = ctk.CTkSlider(scroll, from_=3, to=15, number_of_steps=24)
        self.interval.set(self.cfg.get("vision_interval_sec", 6.0))
        self.interval.pack(fill="x", pady=2)
        self.interval_label = ctk.CTkLabel(scroll, text=f"Interval: {self.interval.get():.1f}s")
        self.interval_label.pack(anchor="w")
        self.interval.configure(command=lambda v: self.interval_label.configure(
            text=f"Interval: {float(v):.1f}s"))

        section("VOLUME")
        self.speech_vol = ctk.CTkSlider(scroll, from_=0, to=1)
        self.speech_vol.set(self.cfg.get("speech_volume", 0.85))
        self.speech_vol.pack(fill="x", pady=2)

        ctk.CTkButton(
            scroll, text="SAVE SETTINGS", height=36,
            fg_color="#1a5a3a", hover_color="#2a7a4a",
            command=self._save
        ).pack(fill="x", pady=16)

    def _browse(self, entry):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("GGUF models", "*.gguf"), ("All files", "*.*")]
        )
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _check_text(self):
        ok, msg = self._check_model_file(self.text_path.get())
        self.text_status.configure(text=msg, text_color="#00FF66" if ok else "#FF5555")

    def _check_vision(self):
        ok, msg = self._check_model_file(self.vis_path.get())
        mm = self.mmproj_path.get().strip()
        if mm:
            mok, mmsg = self._check_model_file(mm)
            msg = f"{msg} | mmproj: {mmsg}"
            if not mok:
                ok = False
        self.vis_status.configure(text=msg, text_color="#00FF66" if ok else "#FF5555")

    def _load_text(self):
        if self._loading:
            self.text_status.configure(text="Busy – wait", text_color="#FFB703")
            return
        import threading
        self._loading = True
        self.text_status.configure(text="Loading…", text_color="#FFB703")

        def worker():
            ok = self.brain.load_model(
                self.text_path.get(),
                status_callback=lambda m: self.after(0, lambda: self.text_status.configure(text=m))
            )
            self.after(0, lambda: self.text_status.configure(
                text="LOADED ✓" if ok else "FAILED",
                text_color="#00FF66" if ok else "#FF5555"
            ))
            self._loading = False

        threading.Thread(target=worker, daemon=True).start()

    def _load_vision(self):
        if self._loading:
            self.vis_status.configure(text="Busy – wait", text_color="#FFB703")
            return
        import threading
        self._loading = True
        self.vis_status.configure(text="Loading…", text_color="#FFB703")

        def worker():
            ok = self.brain.load_vision_model(
                self.vis_path.get(),
                self.mmproj_path.get().strip() or None,
                status_callback=lambda m: self.after(0, lambda: self.vis_status.configure(text=m))
            )
            self.after(0, lambda: self.vis_status.configure(
                text="LOADED ✓" if ok else "FAILED",
                text_color="#00FF66" if ok else "#FF5555"
            ))
            self._loading = False

        threading.Thread(target=worker, daemon=True).start()

    def _save(self):
        self.cfg["text_model_path"] = self.text_path.get().strip()
        self.cfg["vision_model_path"] = self.vis_path.get().strip()
        self.cfg["vision_mmproj_path"] = self.mmproj_path.get().strip()
        self.cfg["vision_enabled"] = bool(self.vision_enabled.get())
        self.cfg["vision_interval_sec"] = float(self.interval.get())
        self.cfg["speech_volume"] = float(self.speech_vol.get())
        if self.on_save:
            self.on_save(self.cfg)

class VisionStatusHUD(HUDPanel):
    def __init__(self, master, on_close=None, on_extract=None):
        super().__init__(master, "Eyes – Live Vision", width=400, height=300,
                         on_close=on_close, on_extract=on_extract)
        self.status = ctk.CTkLabel(
            self.content, text="Waiting for first look…",
            font=("Segoe UI", 12), text_color="#8ab4d4",
            wraplength=360, justify="left"
        )
        self.status.pack(fill="both", expand=True, padx=4, pady=8)

    def update_summary(self, text: str):
        try:
            self.status.configure(text=text)
        except Exception:
            pass
