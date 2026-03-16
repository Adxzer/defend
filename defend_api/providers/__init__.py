from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Dict

from .base import BaseProvider

_registry: Dict[str, BaseProvider] = {}
_loaded: bool = False


def load_providers() -> None:
    """Auto-discover provider subpackages and instantiate BaseProvider subclasses."""
    global _loaded
    if _loaded:
        return

    providers_dir = Path(__file__).parent
    package = __name__

    for module_info in pkgutil.iter_modules([str(providers_dir)]):
        name = module_info.name
        if name in {"base", "orchestrator"}:
            continue

        if not module_info.ispkg:
            continue

        module_path = f"{package}.{name}.provider"
        module = importlib.import_module(module_path)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseProvider)
                and attr is not BaseProvider
            ):
                instance = attr()
                _registry[instance.name] = instance

    _loaded = True


def get_provider(name: str) -> BaseProvider:
    if not _loaded:
        load_providers()

    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise ValueError(f"Unknown provider '{name}'. Available providers: {available}")
    return _registry[name]


def get_all_providers() -> Dict[str, BaseProvider]:
    if not _loaded:
        load_providers()
    return dict(_registry)

