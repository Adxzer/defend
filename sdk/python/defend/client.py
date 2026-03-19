from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Mapping, Optional

import httpx

from .exceptions import DefendBlockedError, DefendConnectionError, DefendHTTPError
from .models import GuardResult, HealthResponse, Session


def _normalize_base_url(base_url: str) -> str:
    """
    Normalize a base URL such that it includes the `/v1` API prefix.

    The server mounts all routers under `/v1` (see `api.main`).
    """

    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


class Client:
    """
    Synchronous HTTP client for the Defend API.

    The base installation intentionally depends only on `httpx` and `pydantic`.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        provider: str | None = None,
        modules: Optional[Iterable[str]] = None,
        confidence_threshold: float | None = None,
        timeout: float | httpx.Timeout = 10.0,
        *,
        raise_on_block: bool = False,
    ) -> None:
        """
        Create a new client.

        Args:
            api_key: Defend API key (sent as `Authorization: Bearer ...`). The current
                server may not enforce auth, but the header is included for forward-compat.
            base_url: Root URL of the server, with or without `/v1`.
            provider: Reserved for future server-side configuration; currently sent as metadata.
            modules: Reserved for future server-side configuration; currently sent as metadata.
            confidence_threshold: Reserved for future server-side configuration; currently sent as metadata.
            timeout: HTTP timeout in seconds (float) or `httpx.Timeout`.
            raise_on_block: If true, raise `DefendBlockedError` when `result.blocked` is true.
        """

        self._api_key = api_key
        self._base_url = _normalize_base_url(base_url)
        self._timeout = timeout
        self._raise_on_block = raise_on_block

        self._default_metadata: Dict[str, Any] = {}
        if provider is not None:
            self._default_metadata["provider"] = provider
        if modules is not None:
            self._default_metadata["modules"] = list(modules)
        if confidence_threshold is not None:
            self._default_metadata["confidence_threshold"] = confidence_threshold

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

        self._last_session_id: Optional[str] = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _request_json(
        self, method: str, path: str, *, json_body: Optional[Mapping[str, Any]] = None
    ) -> Any:
        try:
            resp = self._client.request(method, path, json=json_body)
        except httpx.RequestError as exc:  # pragma: no cover - environment dependent
            raise DefendConnectionError(f"Failed to connect to Defend at {self._base_url}", details=str(exc)) from exc

        if resp.status_code >= 400:
            payload: Any
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise DefendHTTPError(
                f"Defend API error calling {method} {path}",
                status_code=resp.status_code,
                payload=payload,
                headers=dict(resp.headers),
            )

        # Some endpoints (DELETE) return empty bodies.
        if not resp.content:
            return None

        # Prefer json() but be tolerant.
        try:
            return resp.json()
        except json.JSONDecodeError:
            return resp.text

    def health(self) -> HealthResponse:
        data = self._request_json("GET", "/health")
        return HealthResponse.model_validate(data)

    def input(
        self,
        text: str,
        session_id: str | None = None,
        dry_run: bool = False,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GuardResult:
        merged_meta: Dict[str, Any] = dict(self._default_metadata)
        if metadata:
            merged_meta.update(dict(metadata))
        body: Dict[str, Any] = {"text": text, "session_id": session_id, "metadata": merged_meta}
        if dry_run:
            body["dry_run"] = True

        data = self._request_json("POST", "/guard/input", json_body=body)
        result = GuardResult.model_validate(data)
        self._last_session_id = result.session_id

        if self._raise_on_block and result.blocked:
            raise DefendBlockedError("Input blocked", result=result)

        return result

    def output(
        self,
        text: str,
        session_id: str | None = None,
        dry_run: bool = False,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GuardResult:
        sid = session_id or self._last_session_id
        merged_meta: Dict[str, Any] = dict(self._default_metadata)
        if metadata:
            merged_meta.update(dict(metadata))
        body: Dict[str, Any] = {"text": text, "session_id": sid, "metadata": merged_meta}
        if dry_run:
            body["dry_run"] = True

        data = self._request_json("POST", "/guard/output", json_body=body)
        result = GuardResult.model_validate(data)

        if self._raise_on_block and result.blocked:
            raise DefendBlockedError("Output blocked", result=result)

        return result

    def get_session(self, session_id: str) -> Session:
        data = self._request_json("GET", f"/sessions/{session_id}")
        return Session.model_validate(data)

    def delete_session(self, session_id: str) -> None:
        self._request_json("DELETE", f"/sessions/{session_id}")
        return None


class AsyncClient:
    """
    Asynchronous HTTP client for the Defend API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        provider: str | None = None,
        modules: Optional[Iterable[str]] = None,
        confidence_threshold: float | None = None,
        timeout: float | httpx.Timeout = 10.0,
        *,
        raise_on_block: bool = False,
    ) -> None:
        self._api_key = api_key
        self._base_url = _normalize_base_url(base_url)
        self._timeout = timeout
        self._raise_on_block = raise_on_block

        self._default_metadata: Dict[str, Any] = {}
        if provider is not None:
            self._default_metadata["provider"] = provider
        if modules is not None:
            self._default_metadata["modules"] = list(modules)
        if confidence_threshold is not None:
            self._default_metadata["confidence_threshold"] = confidence_threshold

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._last_session_id: Optional[str] = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.aclose()

    async def _request_json(
        self, method: str, path: str, *, json_body: Optional[Mapping[str, Any]] = None
    ) -> Any:
        try:
            resp = await self._client.request(method, path, json=json_body)
        except httpx.RequestError as exc:  # pragma: no cover - environment dependent
            raise DefendConnectionError(f"Failed to connect to Defend at {self._base_url}", details=str(exc)) from exc

        if resp.status_code >= 400:
            payload: Any
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise DefendHTTPError(
                f"Defend API error calling {method} {path}",
                status_code=resp.status_code,
                payload=payload,
                headers=dict(resp.headers),
            )

        if not resp.content:
            return None

        try:
            return resp.json()
        except json.JSONDecodeError:
            return resp.text

    async def health(self) -> HealthResponse:
        data = await self._request_json("GET", "/health")
        return HealthResponse.model_validate(data)

    async def input(
        self,
        text: str,
        session_id: str | None = None,
        dry_run: bool = False,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GuardResult:
        merged_meta: Dict[str, Any] = dict(self._default_metadata)
        if metadata:
            merged_meta.update(dict(metadata))
        body: Dict[str, Any] = {"text": text, "session_id": session_id, "metadata": merged_meta}
        if dry_run:
            body["dry_run"] = True

        data = await self._request_json("POST", "/guard/input", json_body=body)
        result = GuardResult.model_validate(data)
        self._last_session_id = result.session_id

        if self._raise_on_block and result.blocked:
            raise DefendBlockedError("Input blocked", result=result)

        return result

    async def output(
        self,
        text: str,
        session_id: str | None = None,
        dry_run: bool = False,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> GuardResult:
        sid = session_id or self._last_session_id
        merged_meta: Dict[str, Any] = dict(self._default_metadata)
        if metadata:
            merged_meta.update(dict(metadata))
        body: Dict[str, Any] = {"text": text, "session_id": sid, "metadata": merged_meta}
        if dry_run:
            body["dry_run"] = True

        data = await self._request_json("POST", "/guard/output", json_body=body)
        result = GuardResult.model_validate(data)

        if self._raise_on_block and result.blocked:
            raise DefendBlockedError("Output blocked", result=result)

        return result

    async def get_session(self, session_id: str) -> Session:
        data = await self._request_json("GET", f"/sessions/{session_id}")
        return Session.model_validate(data)

    async def delete_session(self, session_id: str) -> None:
        await self._request_json("DELETE", f"/sessions/{session_id}")
        return None

