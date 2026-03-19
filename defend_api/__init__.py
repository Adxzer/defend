"""
Internal Defend API namespace.

This module exposes the FastAPI server under `defend_api`, which is the canonical
import path for the Defend microservice in this repository layout.
"""

from .main import create_app

__all__ = ["create_app"]


