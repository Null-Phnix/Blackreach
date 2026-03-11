#!/usr/bin/env python3
"""
Blackreach entry point.

Usage:
    python blackreach.py "your goal here"
    python blackreach.py --headless "search for something"
"""

import sys
from pathlib import Path

# Add blackreach to path
sys.path.insert(0, str(Path(__file__).parent))

from blackreach.cli import main

if __name__ == "__main__":
    main()
