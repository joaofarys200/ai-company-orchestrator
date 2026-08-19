"""
JARVIS OS — Phase 10: Controlled Real-World Value Generation Runner (Root Entrypoint)
"""

import asyncio
import os
import sys

# Ensure repository root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from scripts.run_phase10_validation import main

if __name__ == "__main__":
    asyncio.run(main())
