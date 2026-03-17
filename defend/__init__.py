"""
DEFEND Python SDK.

Base install (`pip install defend`) provides:
- `Client` / `AsyncClient` for calling a running DEFEND server.
- Optional framework middleware helpers with lazy imports.
"""

from .client import AsyncClient, Client
from .middleware import DefendMiddleware, defend_required

__all__ = ["Client", "AsyncClient", "DefendMiddleware", "defend_required"]

