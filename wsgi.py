"""
WSGI Entry Point for Production Deployment
Usage:
    gunicorn wsgi:app
    waitress-serve --port=5000 wsgi:app
"""

from app import app

if __name__ == "__main__":
    app.run()
