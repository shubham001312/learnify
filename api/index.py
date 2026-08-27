import os
import sys

# Make the project root importable so `backend.main` resolves.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.main import app  # noqa: E402

# Vercel serves this ASGI app for all /api/* routes (see vercel.json).
