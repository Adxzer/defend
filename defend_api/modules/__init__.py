from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import BaseModule

_registry: Dict[str, Type[BaseModule]] = {}
_loaded: bool = False


def load_modules() -> None:
    """Auto-discover guard module subpackages and register BaseModule subclasses.

    We scan the filesystem for directories containing either `module.py` (input/both)
    and/or `output_module.py` (output/both) so module packages do not strictly need
    an `__init__.py`.
    """
    global _loaded
    if _loaded:
        return

    modules_dir = Path(__file__).parent
    package = __name__

    for child in modules_dir.iterdir():
        if not child.is_dir():
            continue

        name = child.name
        if name in {"base", "__pycache__"}:
            continue

        for suffix in ("module", "output_module"):
            if not (child / f"{suffix}.py").exists():
                continue

            module_path = f"{package}.{name}.{suffix}"
            module = importlib.import_module(module_path)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseModule)
                    and attr is not BaseModule
                ):
                    module_cls: Type[BaseModule] = attr
                    module_name = getattr(module_cls, "name", None)
                    if not isinstance(module_name, str) or not module_name:
                        continue
                    _registry[module_name] = module_cls

    _loaded = True


def get_module(name: str) -> Type[BaseModule]:
    if not _loaded:
        load_modules()
    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise ValueError(f"Unknown module '{name}'. Available modules: {available}")
    return _registry[name]


def get_active_modules() -> Dict[str, Type[BaseModule]]:
    if not _loaded:
        load_modules()
    return dict(_registry)


def instantiate_module(name: str, config: Optional[Dict[str, Any]] = None) -> BaseModule:
    """Instantiate a module by name with optional kwargs config.

    - For simple modules (no args), config is ignored.
    - For configurable modules, kwargs are passed through (best-effort).
    """
    module_cls = get_module(name)
    kwargs = dict(config or {})

    try:
        return module_cls(**kwargs)
    except TypeError:
        # If constructor doesn't accept kwargs (or config mismatched), fall back to no-arg.
        return module_cls()


def parse_module_spec(spec: Any) -> tuple[str, Dict[str, Any]]:
    """Parse a module spec from YAML.

    Supported forms:
    - \"injection\"
    - {\"topic\": {\"allowed_topics\": [...]}}
    - {\"custom\": {\"prompt\": \"...\"}}
    """
    if isinstance(spec, str):
        return spec, {}
    if isinstance(spec, dict) and len(spec) == 1:
        (name, cfg) = next(iter(spec.items()))
        if isinstance(name, str) and isinstance(cfg, dict):
            return name, dict(cfg)
    raise ValueError(f"Invalid module spec: {spec!r}")


def build_modules_from_specs(specs: List[Any]) -> List[BaseModule]:
    modules: List[BaseModule] = []
    for spec in specs:
        name, cfg = parse_module_spec(spec)
        modules.append(instantiate_module(name, cfg))
    return modules


def get_modules_for_input() -> List[BaseModule]:
    if not _loaded:
        load_modules()
    # Unconfigured list (for compatibility). Prefer build_modules_from_specs for configured instances.
    out: List[BaseModule] = []
    for cls in _registry.values():
        direction = getattr(cls, "direction", "input")
        if direction in ("input", "both"):
            out.append(cls())
    return out


def get_modules_for_output() -> List[BaseModule]:
    if not _loaded:
        load_modules()
    out: List[BaseModule] = []
    for cls in _registry.values():
        direction = getattr(cls, "direction", "input")
        if direction in ("output", "both"):
            out.append(cls())
    return out

