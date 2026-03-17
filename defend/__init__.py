"""
Defend Python SDK and API.

Base install (`pip install defend`) provides:
- `Client` / `AsyncClient` for calling a running Defend server.
- Optional framework middleware helpers with lazy imports.
- `create_app` for embedding the Defend FastAPI service directly.
"""

from .client import AsyncClient, Client
from .middleware import DefendMiddleware, defend_required
from .api import create_app

__all__ = ["Client", "AsyncClient", "DefendMiddleware", "defend_required", "create_app"]

