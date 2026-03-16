from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from .exceptions import BlockedError, DefendError, ProviderError
from .models import GuardResult


class Client:
    def __init__(
        self,
        api_key: str,
        provider: str = "defend",
        modules: List[Any] | None = None,
        output_modules: List[Any] | None = None,
        output_provider: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        block_message: Optional[str] = None,
        raise_on_block: bool = False,
    ) -> None:
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._config: Dict[str, Any] = {
            "provider": provider,
            "modules": modules or [],
            "output_modules": output_modules or [],
            "output_provider": output_provider or provider,
            "base_url": base_url,
        }
        self._block_message = block_message
        self._raise_on_block = raise_on_block
        self._last_session_id: Optional[str] = None

    def _handle_response(self, resp: httpx.Response) -> Dict[str, Any]:
        if resp.status_code >= 400:
            raise ProviderError(f"DEFEND error {resp.status_code}", response=resp.json())
        return resp.json()

    def input(self, text: str, metadata: Optional[dict] = None) -> GuardResult:
        body = {
            "text": text,
            "metadata": metadata,
        }
        resp = self._client.post("/guard/input", json=body)
        data = self._handle_response(resp)
        result = GuardResult(**data)
        self._last_session_id = result.session_id

        if self._raise_on_block and result.blocked:
            raise BlockedError("Input blocked", response=result)
        return result

    def output(
        self,
        text: str,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> GuardResult:
        sid = session_id or self._last_session_id
        body = {
            "text": text,
            "session_id": sid,
            "metadata": metadata,
        }
        resp = self._client.post("/guard/output", json=body)
        data = self._handle_response(resp)
        result = GuardResult(**data)

        if self._raise_on_block and result.blocked:
            raise BlockedError("Output blocked", response=result)
        return result


class AsyncClient(Client):
    def __init__(
        self,
        api_key: str,
        provider: str = "defend",
        modules: List[Any] | None = None,
        output_modules: List[Any] | None = None,
        output_provider: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        block_message: Optional[str] = None,
        raise_on_block: bool = False,
    ) -> None:
        super().__init__(
            api_key=api_key,
            provider=provider,
            modules=modules,
            output_modules=output_modules,
            output_provider=output_provider,
            base_url=base_url,
            block_message=block_message,
            raise_on_block=raise_on_block,
        )
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def input(self, text: str, metadata: Optional[dict] = None) -> GuardResult:  # type: ignore[override]
        body = {
            "text": text,
            "metadata": metadata,
        }
        resp = await self._client.post("/guard/input", json=body)
        data = self._handle_response(resp)  # type: ignore[arg-type]
        result = GuardResult(**data)
        self._last_session_id = result.session_id

        if self._raise_on_block and result.blocked:
            raise BlockedError("Input blocked", response=result)
        return result

    async def output(  # type: ignore[override]
        self,
        text: str,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> GuardResult:
        sid = session_id or self._last_session_id
        body = {
            "text": text,
            "session_id": sid,
            "metadata": metadata,
        }
        resp = await self._client.post("/guard/output", json=body)
        data = self._handle_response(resp)  # type: ignore[arg-type]
        result = GuardResult(**data)

        if self._raise_on_block and result.blocked:
            raise BlockedError("Output blocked", response=result)
        return result

