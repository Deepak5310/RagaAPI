"""Vercel requires 'app' to be defined at module level for ASGI"""

from main import app

__all__ = ["app"]
