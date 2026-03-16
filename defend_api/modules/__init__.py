from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List

from .base import BaseModule

_registry: Dict[str, BaseModule] = {}
_loaded: bool = False


def load_modules() -> None:
    """Auto-discover module subpackages and instantiate BaseModule subclasses."""
    global _loaded
    if _loaded:
        return

    modules_dir = Path(__file__).parent
    package = __name__

    for module_info in pkgutil.iter_modules([str(modules_dir)]):
        name = module_info.name
        if name == "base":
            continue
        if not module_info.ispkg:
            continue

        module_path = f"{package}.{name}.module"
        module = importlib.import_module(module_path)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseModule)
                and attr is not BaseModule
            ):
                instance = attr()
                _registry[instance.name] = instance

    _loaded = True


def get_module(name: str) -> BaseModule:
    if not _loaded:
        load_modules()
    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise ValueError(f"Unknown module '{name}'. Available modules: {available}")
    return _registry[name]


def get_active_modules() -> Dict[str, BaseModule]:
    if not _loaded:
        load_modules()
    return dict(_registry)


def get_modules_for_input() -> List[BaseModule]:
    if not _loaded:
        load_modules()
    return [m for m in _registry.values() if m.direction in ("input", "both")]


def get_modules_for_output() -> List[BaseModule]:
    if not _loaded:
        load_modules()
    return [m for m in _registry.values() if m.direction in ("output", "both")]

