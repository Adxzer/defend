import os
from typing import Any, Dict

import httpx


DEFEND_API_URL = os.environ.get("DEFEND_API_URL", "http://localhost:8000")


def classify(text: str, session_id: str | None = None, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"text": text}
    if session_id is not None:
        payload["session_id"] = session_id
    if metadata is not None:
        payload["metadata"] = metadata

    url = f"{DEFEND_API_URL}/classify"
    response = httpx.post(url, json=payload, timeout=10.0)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    result = classify("Hello world", session_id="demo-session")
    print(result)

