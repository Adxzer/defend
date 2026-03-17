from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, TypeVar, cast

from .client import Client
from .models import GuardResult

T = TypeVar("T")


class SessionKey(Protocol):
    """
    Extract a session id from a framework request object.
    """

    def __call__(self, request: Any) -> Optional[str]: ...


OnBlock = Callable[[GuardResult, Any], Any]


def _default_session_key(_: Any) -> Optional[str]:
    return None


def _safe_json_loads(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _extract_text_from_body(body: Any) -> Optional[str]:
    """
    Best-effort extraction of a 'text' field from arbitrary request bodies.
    """

    if body is None:
        return None
    if isinstance(body, str):
        return body
    if isinstance(body, bytes):
        try:
            return body.decode("utf-8", errors="replace")
        except Exception:
            return None
    if isinstance(body, dict):
        value = body.get("text")
        if isinstance(value, str):
            return value
    return None


class DefendMiddleware:  # intentionally not importing Starlette at module import time
    """
    Starlette/FastAPI middleware that guards request and response bodies.

    This class is implemented with *lazy imports* so `pip install defend` stays lightweight.
    To use it, install extras that provide Starlette/FastAPI and mount it in your app.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        # Create a real BaseHTTPMiddleware subclass at runtime.
        try:
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.requests import Request
            from starlette.responses import JSONResponse, Response
        except Exception as exc:  # pragma: no cover - depends on extras
            raise RuntimeError(
                "DefendMiddleware requires Starlette/FastAPI. Install with `pip install defend[server]` "
                "or install your framework dependencies separately."
            ) from exc

        api_key: str = kwargs.pop("api_key")
        modules = kwargs.pop("modules", None)
        session_key: SessionKey = kwargs.pop("session_key", _default_session_key)
        on_block: OnBlock | None = kwargs.pop("on_block", None)
        base_url: str = kwargs.pop("base_url", "http://localhost:8000")
        timeout: float = kwargs.pop("timeout", 10.0)

        guard = Client(api_key=api_key, base_url=base_url, modules=modules, timeout=timeout)

        class _Impl(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
                raw_body = await request.body()
                parsed = _safe_json_loads(raw_body) if raw_body else None
                text = _extract_text_from_body(parsed) or _extract_text_from_body(raw_body)
                sid = session_key(request)

                if text is not None:
                    result = guard.input(text, session_id=sid)
                    if result.blocked:
                        if on_block is not None:
                            try:
                                on_block(result, request)
                            except Exception:
                                # Never allow callbacks to crash the middleware path.
                                pass
                        return JSONResponse(result.error_response(), status_code=403)

                response = await call_next(request)

                # Best-effort output guard. Avoid breaking streaming responses.
                content_type = response.headers.get("content-type", "")
                if "text" in content_type or "json" in content_type:
                    try:
                        body_bytes = b"".join([chunk async for chunk in response.body_iterator])
                        parsed_out = _safe_json_loads(body_bytes) if body_bytes else None
                        out_text = _extract_text_from_body(parsed_out) or _extract_text_from_body(body_bytes)
                        if out_text is not None:
                            out_res = guard.output(out_text, session_id=sid)
                            if out_res.blocked:
                                if on_block is not None:
                                    try:
                                        on_block(out_res, request)
                                    except Exception:
                                        pass
                                return JSONResponse(out_res.error_response(), status_code=403)

                        # Reconstruct the response with the original body
                        return Response(
                            content=body_bytes,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            media_type=response.media_type,
                        )
                    except Exception:
                        return response

                return response

        return _Impl(*args, **kwargs)


F = TypeVar("F", bound=Callable[..., Any])


def defend_required(
    *,
    api_key: str,
    modules: Optional[list[str]] = None,
    session_key: SessionKey = _default_session_key,
    on_block: OnBlock | None = None,
    base_url: str = "http://localhost:8000",
    timeout: float = 10.0,
) -> Callable[[F], F]:
    """
    Flask decorator that guards requests before calling the view function.

    Requires Flask at runtime (lazy import). If Flask is not installed, raises a RuntimeError
    with an installation hint.
    """

    try:
        from flask import Response as FlaskResponse
        from flask import jsonify, request
    except Exception as exc:  # pragma: no cover - depends on extras
        raise RuntimeError(
            "defend_required requires Flask. Install with `pip install defend[flask]` "
            "or install Flask in your environment."
        ) from exc

    guard = Client(api_key=api_key, base_url=base_url, modules=modules, timeout=timeout)

    def decorator(fn: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            sid = session_key(request)
            body: Any = request.get_json(silent=True)
            text = _extract_text_from_body(body)
            if text is None:
                # Fall back to raw body for non-JSON requests.
                raw = request.get_data(cache=True)
                text = _extract_text_from_body(raw)

            if text is not None:
                result = guard.input(text, session_id=sid)
                if result.blocked:
                    if on_block is not None:
                        try:
                            on_block(result, request)
                        except Exception:
                            pass
                    return jsonify(result.error_response()), 403

            return fn(*args, **kwargs)

        return cast(F, wrapper)

    return decorator

