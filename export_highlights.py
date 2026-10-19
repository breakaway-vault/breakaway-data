#!/usr/bin/env python3
"""Shortcut: same as `python breakaway.py all` (fetch new/missing, covers, build xlsx, package zip).
Any flags are passed through, e.g. `python export_highlights.py --refresh --concurrency 4`."""
import os, subprocess, sys
sys.exit(subprocess.call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "breakaway.py"), "all", *sys.argv[1:]]))
