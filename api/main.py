import sys
import os

# Insert backend root directory to Python module search path
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.main import app

# Vercel Serverless Function looks for the ASGI/WSGI app instance
