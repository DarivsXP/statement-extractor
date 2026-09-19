"""
Compatibility entrypoint for Render.
Exports the FastAPI ASGI app for Uvicorn / Gunicorn.
"""
from server import app, application

__all__ = ["app", "application"]
