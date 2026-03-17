from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from ..session import get_session_backend


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    backend = get_session_backend()
    state = await backend.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return JSONResponse(
        content={
            "session_id": state.session_id,
            "turns": len(state.history),
            "risk_score": state.rolling_score,
            "peak_score": state.peak_score,
            "history": state.history,
        }
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> Response:
    backend = get_session_backend()
    await backend.delete(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

