"""
Defend Python SDK.

Base install (`pip install defend`) provides:
- `Client` / `AsyncClient` for calling a running Defend server.
"""

from .client import AsyncClient, Client

__all__ = ["Client", "AsyncClient"]

