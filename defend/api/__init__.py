"""
Internal DEFEND API namespace.

This module exposes the FastAPI server under `defend.api`, which is the
canonical import path for the DEFEND microservice.
"""

from .main import create_app

__all__ = ["create_app"]


