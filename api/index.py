"""
api/index.py - Vercel WSGI entry point for AI Content Detector Flask app.
"""
import sys
import os

# Add project root to path so imports from app.py, models.py, detector.py work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel expects a callable named 'app' or 'handler'
# The Flask app object is itself a WSGI callable
