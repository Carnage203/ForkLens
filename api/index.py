"""Vercel entrypoint: the Python runtime serves the ASGI ``app`` exported here."""
from backend.main import app  # noqa: F401
