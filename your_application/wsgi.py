"""
Compatibility entrypoint for Render default start command (gunicorn your_application.wsgi:app).
"""
from server import app, application

__all__ = ["app", "application"]
