#!/usr/bin/env python3
"""
Simple launcher for JARVIS v2.
Place this next to the jarvis_v2 folder and run:
    python run_jarvis_v2.py
"""
import sys
import os

# Make sure we can import the package
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from jarvis_v2.main import main

if __name__ == "__main__":
    main()
