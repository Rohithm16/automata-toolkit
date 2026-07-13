"""Compatibility wrapper that exposes the real FastAPI app as `automata_toolkit.app`.

This lets `python -m uvicorn automata_toolkit.app:app --reload` work even when
the current working directory is the outer `automata_toolkit` folder.
"""

from __future__ import annotations

from app import app
