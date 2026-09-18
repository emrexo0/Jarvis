"""
JARVIS v2 – Soft starfield + supernovas + custom background manager
(Preserved and slightly cleaned from original)
"""
import math
import random
import time
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk

from .config import STAR_COLORS, DUST_BASE, SUPERNOVA_COLORS, logger

try:
    from ffpyplayer.player import MediaPlayer
    HAS_FFPY = True
except ImportError:
    HAS_FFPY = False


class BackgroundAnimator:
    def __init__(self, canvas: ctk.CTkCanvas, star_count=40, dust_count=60):
        self.canvas = canvas
        self.target_stars = star_count
        self.target_dust = dust_count
        self.stars = []
        self.dust = []
        self.supernovas = []
        self._running = False
        self._after_id = None
        self._last_w = 0
        self._last_h = 0
        self._supernova_timer = 0.0
        self._next_supernova = random.uniform(8.0, 18.0)

    def start(self):
        if self._running:
            return
        self._running = True
        self._ensure_size()
        self._spawn_initial()
        self._tick()

    def stop(self):
        self._running = False
        if self._after_id:
            try:
                self.canvas.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        for s in self.stars:
            try:
                self.canvas.delete(s["id"])
            except Exception:
                pass
        for p in self.dust:
            try:
                self.canvas.delete(p["id"])
            except Exception:
                pass
        for sn in self.supernovas:
            self._kill_supernova(sn)
        self.stars.clear()
        self.dust.clear()
        self.supernovas.clear()

    def _ensure_size(self):
        try:
            w = max(self.canvas.winfo_width(), 100)
            h = max(self.canvas.winfo_height(), 100)
        except Exception:
            w, h = 800, 600
        if abs(w - self._last_w) > 40 or abs(h - self._last_h) > 40:
            self._last_w, self._last_h = w, h
            while len(self.stars) < self.target_stars:
                self._spawn_star(w, h, fade_in=True)
            while len(self.dust) < self.target_dust:
                self._spawn_dust(w, h, fade_in=True)

    def _spawn_initial(self):
        w = max(self._last_w, 800)
        h = max(self._last_h, 600)
        for _ in range(self.target_stars):
            self._spawn_star(w, h, fade_in=random.random() > 0.3)
        for _ in range(self.target_dust):
            self._spawn_dust(w, h, fade_in=random.random() > 0.3)

    def _spawn_star(self, w, h, fade_in=True):
        x = random.randint(0, max(1, w))
        y = random.randint(0, max(1, h))
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.35, 1.4)
        length = random.randint(8, 22)
        color = random.choice(STAR_COLORS)
        line = self.canvas.create_line(
            x, y,
            x + length * math.cos(angle),
            y + length * math.sin(angle),
            fill=color, width=1
        )
        life = random.uniform(4.0, 12.0)
        self.stars.append({
            "id": line, "x": x, "y": y,
            "dx": speed * math.cos(angle),
            "dy": speed * math.sin(angle),
            "len": length, "angle": angle,
            "color": color,
            "age": 0.0, "life": life,
            "fade_in": 0.6 if fade_in else 0.0,
            "fade_out": 1.2,
            "alpha": 0.0 if fade_in else 1.0,
        })

    def _spawn_dust(self, w, h, fade_in=True):
        x = random.randint(-200, w + 200)
        y = random.randint(0, max(1, h))
        size = random.uniform(0.7, 2.0)
        base_alpha = random.uniform(0.10, 0.30)
        r = int(DUST_BASE[0] * base_alpha + 8)
        g = int(DUST_BASE[1] * base_alpha + 18)
        b = int(DUST_BASE[2] * base_alpha + 28)
        color = f"#{r:02x}{g:02x}{b:02x}"
        dot = self.canvas.create_oval(
            x - size, y - size, x + size, y + size,
            fill=color, outline=""
        )
        life = random.uniform(5.0, 14.0)
        self.dust.append({
            "id": dot, "x": x, "y": y,
            "speed": random.uniform(0.2, 0.85),
            "size": size,
            "base_color": (r, g, b),
            "age": 0.0, "life": life,
            "fade_in": 0.8 if fade_in else 0.0,
            "fade_out": 1.4,
            "alpha": 0.0 if fade_in else 1.0,
        })

    def _spawn_supernova(self, w, h):
        cx = random.randint(int(w * 0.15), int(w * 0.85))
        cy = random.randint(int(h * 0.15), int(h * 0.85))
        max_r = random.uniform(90, 180)

        core = self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                       fill="#ffffff", outline="#ffbf69", width=2)
        wave = self.canvas.create_oval(cx, cy, cx, cy, outline="#ff9f1c", width=2)

        debris = []
        for _ in range(random.randint(18, 32)):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(2.5, 7.5)
            size = random.uniform(1.2, 3.5)
            col = random.choice(SUPERNOVA_COLORS)
            pid = self.canvas.create_oval(cx - size, cy - size, cx + size, cy + size,
                                          fill=col, outline="")
            debris.append({
                "id": pid, "x": cx, "y": cy,
                "dx": math.cos(ang) * spd, "dy": math.sin(ang) * spd,
                "size": size, "color": col,
                "life": random.uniform(3.2, 6.5), "age": 0.0
            })

        dust_cloud = []
        for _ in range(random.randint(25, 40)):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(0.6, 2.8)
            size = random.uniform(0.8, 2.2)
            alpha = random.uniform(0.25, 0.55)
            r = int(80 + 120 * alpha)
            g = int(40 + 80 * alpha)
            b = int(20 + 40 * alpha)
            col = f"#{r:02x}{g:02x}{b:02x}"
            pid = self.canvas.create_oval(cx - size, cy - size, cx + size, cy + size,
                                          fill=col, outline="")
            dust_cloud.append({
                "id": pid, "x": cx, "y": cy,
                "dx": math.cos(ang) * spd, "dy": math.sin(ang) * spd,
                "size": size, "base_color": (r, g, b),
                "life": random.uniform(4.5, 8.5), "age": 0.0, "alpha": alpha
            })

        ejected = []
        for _ in range(random.randint(7, 14)):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(3.0, 8.0)
            length = random.randint(10, 20)
            col = random.choice(["#ffffff", "#a0e7ff", "#ffbf69"])
            lid = self.canvas.create_line(cx, cy,
                                          cx + length * math.cos(ang),
                                          cy + length * math.sin(ang),
                                          fill=col, width=1)
            ejected.append({
                "id": lid, "x": cx, "y": cy,
                "dx": math.cos(ang) * spd, "dy": math.sin(ang) * spd,
                "len": length, "angle": ang, "color": col,
                "life": random.uniform(5.0, 11.0), "fade_out": 1.8, "age": 0.0
            })

        sn = {
            "cx": cx, "cy": cy, "core_id": core, "wave_id": wave,
            "max_r": max_r, "age": 0.0, "life": 5.5,
            "debris": debris, "dust": dust_cloud, "ejected": ejected, "phase": 0
        }
        self.supernovas.append(sn)

    def _kill_supernova(self, sn):
        for key in ("core_id", "wave_id"):
            try:
                self.canvas.delete(sn[key])
            except Exception:
                pass
        for group in ("debris", "dust", "ejected"):
            for item in sn.get(group, []):
                try:
                    self.canvas.delete(item["id"])
                except Exception:
                    pass

    def _alpha_color(self, hex_color, alpha):
        try:
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            br, bg, bb = 8, 12, 20
            r = int(br + (r - br) * alpha)
            g = int(bg + (g - bg) * alpha)
            b = int(bb + (b - bb) * alpha)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _tick(self):
        if not self._running:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return

        dt = 0.055
        self._ensure_size()
        w = self._last_w or 800
        h = self._last_h or 600

        # Stars
        dead_stars = []
        for s in self.stars:
            s["age"] += dt
            if s["age"] < s["fade_in"]:
                s["alpha"] = s["age"] / max(0.01, s["fade_in"])
            elif s["age"] > s["life"] - s["fade_out"]:
                remain = s["life"] - s["age"]
                s["alpha"] = max(0.0, remain / max(0.01, s["fade_out"]))
            else:
                s["alpha"] = 1.0

            if s["age"] >= s["life"] or s["alpha"] <= 0.01:
                try:
                    self.canvas.delete(s["id"])
                except Exception:
                    pass
                dead_stars.append(s)
                continue

            s["x"] += s["dx"]
            s["y"] += s["dy"]
            ex = s["x"] + s["len"] * math.cos(s["angle"])
            ey = s["y"] + s["len"] * math.sin(s["angle"])
            try:
                self.canvas.coords(s["id"], s["x"], s["y"], ex, ey)
                self.canvas.itemconfigure(s["id"], fill=self._alpha_color(s["color"], s["alpha"]))
            except Exception:
                pass

            margin = s["len"] * 2
            if (s["x"] < -margin or s["x"] > w + margin or
                    s["y"] < -margin or s["y"] > h + margin):
                s["x"] = -margin if s["dx"] > 0 else w + margin
                s["y"] = random.randint(0, max(1, h))

        for s in dead_stars:
            self.stars.remove(s)
        while len(self.stars) < self.target_stars:
            self._spawn_star(w, h, fade_in=True)

        # Dust
        dead_dust = []
        for p in self.dust:
            p["age"] += dt
            if p["age"] < p["fade_in"]:
                p["alpha"] = p["age"] / max(0.01, p["fade_in"])
            elif p["age"] > p["life"] - p["fade_out"]:
                remain = p["life"] - p["age"]
                p["alpha"] = max(0.0, remain / max(0.01, p["fade_out"]))
            else:
                p["alpha"] = 1.0

            if p["age"] >= p["life"] or p["alpha"] <= 0.01:
                try:
                    self.canvas.delete(p["id"])
                except Exception:
                    pass
                dead_dust.append(p)
                continue

            p["x"] += p["speed"]
            if p["x"] > w + 60:
                p["x"] = -60
                p["y"] = random.randint(0, max(1, h))
            sz = p["size"]
            try:
                self.canvas.coords(p["id"], p["x"] - sz, p["y"] - sz, p["x"] + sz, p["y"] + sz)
                br, bg, bb = p["base_color"]
                r = int(8 + (br - 8) * p["alpha"])
                g = int(12 + (bg - 12) * p["alpha"])
                b = int(20 + (bb - 20) * p["alpha"])
                self.canvas.itemconfigure(p["id"], fill=f"#{r:02x}{g:02x}{b:02x}")
            except Exception:
                pass

        for p in dead_dust:
            self.dust.remove(p)
        while len(self.dust) < self.target_dust:
            self._spawn_dust(w, h, fade_in=True)

        # Supernovas
        self._supernova_timer += dt
        if self._supernova_timer >= self._next_supernova and len(self.supernovas) < 3:
            self._spawn_supernova(w, h)
            self._supernova_timer = 0.0
            self._next_supernova = random.uniform(7.0, 16.0)

        dead_sn = []
        for sn in self.supernovas:
            sn["age"] += dt
            t = sn["age"]
            life = sn["life"]

            flash_r = 8 + 28 * math.sin(min(1.0, t / 0.35) * math.pi)
            if t > 0.6:
                flash_r *= max(0.0, 1.0 - (t - 0.6) / 0.9)
            try:
                self.canvas.coords(sn["core_id"],
                                   sn["cx"] - flash_r, sn["cy"] - flash_r,
                                   sn["cx"] + flash_r, sn["cy"] + flash_r)
                alpha = max(0.0, 1.0 - t / 1.2)
                col = self._alpha_color("#ffffff", alpha)
                self.canvas.itemconfigure(sn["core_id"], fill=col,
                                          outline=self._alpha_color("#ffbf69", alpha * 0.8))
            except Exception:
                pass

            wave_r = sn["max_r"] * min(1.0, t / 1.1)
            wave_alpha = max(0.0, 1.0 - (t / 1.8))
            try:
                self.canvas.coords(sn["wave_id"],
                                   sn["cx"] - wave_r, sn["cy"] - wave_r,
                                   sn["cx"] + wave_r, sn["cy"] + wave_r)
                width = max(1, int(3 * wave_alpha))
                self.canvas.itemconfigure(sn["wave_id"],
                                          outline=self._alpha_color("#ff9f1c", wave_alpha),
                                          width=width)
            except Exception:
                pass

            for d in sn["debris"]:
                d["age"] += dt
                d["x"] += d["dx"]
                d["y"] += d["dy"]
                d["dx"] *= 0.985
                d["dy"] *= 0.985
                a = max(0.0, 1.0 - d["age"] / d["life"])
                sz = d["size"] * a
                try:
                    self.canvas.coords(d["id"], d["x"] - sz, d["y"] - sz, d["x"] + sz, d["y"] + sz)
                    self.canvas.itemconfigure(d["id"], fill=self._alpha_color(d["color"], a))
                except Exception:
                    pass

            for d in sn["dust"]:
                d["age"] += dt
                d["x"] += d["dx"]
                d["y"] += d["dy"]
                d["dx"] *= 0.97
                d["dy"] *= 0.97
                a = max(0.0, d["alpha"] * (1.0 - d["age"] / d["life"]))
                sz = d["size"] * (0.6 + 0.4 * a)
                try:
                    self.canvas.coords(d["id"], d["x"] - sz, d["y"] - sz, d["x"] + sz, d["y"] + sz)
                    br, bg, bb = d["base_color"]
                    r = int(8 + (br - 8) * a)
                    g = int(12 + (bg - 12) * a)
                    b = int(20 + (bb - 20) * a)
                    self.canvas.itemconfigure(d["id"], fill=f"#{r:02x}{g:02x}{b:02x}")
                except Exception:
                    pass

            for e in sn["ejected"]:
                e["age"] += dt
                e["x"] += e["dx"]
                e["y"] += e["dy"]
                a = max(0.0, 1.0 - e["age"] / e["life"])
                ex = e["x"] + e["len"] * math.cos(e["angle"])
                ey = e["y"] + e["len"] * math.sin(e["angle"])
                try:
                    self.canvas.coords(e["id"], e["x"], e["y"], ex, ey)
                    self.canvas.itemconfigure(e["id"], fill=self._alpha_color(e["color"], a))
                except Exception:
                    pass

            if sn["age"] >= sn["life"]:
                self._kill_supernova(sn)
                dead_sn.append(sn)

        for sn in dead_sn:
            self.supernovas.remove(sn)

        self._after_id = self.canvas.after(55, self._tick)


class BackgroundManager:
    def __init__(self, parent_widget, canvas, width, height):
        self.parent = parent_widget
        self.canvas = canvas
        self.width = width
        self.height = height
        self.current_bg = None
        self.bg_type = None
        self.gif_frames = []
        self.gif_index = 0
        self.gif_after_id = None
        self.video_player = None
        self.video_playing = False
        self.video_after_id = None
        self.photo = None
        self.file_path = None
        self.volume = 0.6

    def load_background(self, file_path):
        if not file_path or not Path(file_path).exists():
            return
        self.stop()
        self.file_path = file_path
        ext = Path(file_path).suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            self._load_image(file_path)
        elif ext == ".gif":
            self._load_gif(file_path)
        elif ext in {".mp4", ".webm", ".avi", ".mkv", ".mov"}:
            self._load_video(file_path)

    def _load_image(self, file_path):
        try:
            img = Image.open(file_path).convert("RGBA")
            img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(img)
            self.current_bg = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
            self.bg_type = "image"
            self.canvas.tag_lower(self.current_bg)
        except Exception as e:
            logger.warning(f"Background image load failed: {e}")

    def _load_gif(self, file_path):
        try:
            img = Image.open(file_path)
            self.gif_frames = []
            for i in range(getattr(img, "n_frames", 1)):
                img.seek(i)
                frame = img.convert("RGBA").resize((self.width, self.height), Image.Resampling.LANCZOS)
                self.gif_frames.append(ImageTk.PhotoImage(frame))
            if self.gif_frames:
                self.photo = self.gif_frames[0]
                self.current_bg = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
                self.bg_type = "gif"
                self.canvas.tag_lower(self.current_bg)
                self.gif_index = 0
                self._animate_gif()
        except Exception as e:
            logger.warning(f"GIF background failed: {e}")

    def _animate_gif(self):
        if self.bg_type != "gif" or not self.gif_frames:
            return
        self.gif_index = (self.gif_index + 1) % len(self.gif_frames)
        try:
            self.canvas.itemconfigure(self.current_bg, image=self.gif_frames[self.gif_index])
        except Exception:
            return
        self.gif_after_id = self.canvas.after(80, self._animate_gif)

    def _load_video(self, file_path):
        if not HAS_FFPY:
            logger.warning("ffpyplayer not available – cannot play video background")
            return
        try:
            self.video_player = MediaPlayer(file_path)
            self.video_playing = True
            self.bg_type = "video"
            self._play_video()
        except Exception as e:
            logger.warning(f"Video background failed: {e}")

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, vol))
        if self.video_player:
            try:
                self.video_player.set_volume(self.volume)
            except Exception:
                pass

    def _play_video(self):
        if not self.video_playing or not self.video_player:
            return
        try:
            frame, val = self.video_player.get_frame()
            if val == "eof":
                self.video_player.seek(0, relative=False)
                frame, val = self.video_player.get_frame()
            if frame is not None:
                img, t = frame
                # Convert to PIL and display
                from ffpyplayer.pic import SWScale
                # Simple path: use raw if possible, else skip complex conversion for stability
                pass  # Full video bg is complex; keep placeholder for now
        except Exception:
            pass
        self.video_after_id = self.canvas.after(33, self._play_video)

    def stop(self):
        if self.gif_after_id:
            try:
                self.canvas.after_cancel(self.gif_after_id)
            except Exception:
                pass
            self.gif_after_id = None
        if self.video_after_id:
            try:
                self.canvas.after_cancel(self.video_after_id)
            except Exception:
                pass
            self.video_after_id = None
        if self.video_player:
            try:
                self.video_player.close_player()
            except Exception:
                pass
            self.video_player = None
        self.video_playing = False
        if self.current_bg:
            try:
                self.canvas.delete(self.current_bg)
            except Exception:
                pass
            self.current_bg = None
        self.gif_frames.clear()
        self.bg_type = None

    def resize(self, width, height):
        self.width = width
        self.height = height
        if self.file_path and self.bg_type in ("image", "gif"):
            self.load_background(self.file_path)
