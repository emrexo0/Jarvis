#!/usr/bin/env python3
"""
JARVIS v2 – Entry point
Flow: Cinematic Intro → Setup (model picker) → Main UI
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

from jarvis_v2.config import logger
from jarvis_v2.intro import IntroSequence
from jarvis_v2.setup import SetupScreen
from jarvis_v2.ui_main import JarvisUI


def main():
    logger.info("JARVIS v2 starting…")

    # Hidden root so intro can be a Toplevel; we destroy it after intro
    root = ctk.CTk()
    root.withdraw()

    def after_intro():
        root.destroy()
        # Setup screen (model selection)
        def after_setup(brain, cfg):
            app = JarvisUI(brain=brain, config=cfg)
            app.mainloop()

        setup = SetupScreen(on_ready_callback=after_setup)
        setup.mainloop()

    intro = IntroSequence(root, on_finished_callback=after_intro)
    root.mainloop()


if __name__ == "__main__":
    main()
