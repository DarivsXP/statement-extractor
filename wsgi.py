"""
WSGI compatibility entrypoint for Render.
"""
from a2wsgi import ASGIMiddleware
from server import app as asgi_app

application = ASGIMiddleware(asgi_app)
app = application
