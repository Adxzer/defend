__all__ = ["create_app"]


def create_app():
    # Lazy import to keep package import lightweight (and test-friendly).
    from .main import create_app as _create_app

    return _create_app()

