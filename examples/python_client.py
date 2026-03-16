import os
from typing import Any, Dict

import httpx

DEFEND_API_URL = os.environ.get("DEFEND_API_URL", "http://localhost:8000")

def guard_input(text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"text": text, "metadata": metadata}
    url = f"{DEFEND_API_URL}/guard/input"
    response = httpx.post(url, json=payload, timeout=10.0)
    response.raise_for_status()
    return response.json()


def guard_output(text: str, session_id: str | None = None, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"text": text, "session_id": session_id, "metadata": metadata}
    url = f"{DEFEND_API_URL}/guard/output"
    response = httpx.post(url, json=payload, timeout=10.0)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    input_result = guard_input("Hello world")
    print("input:", input_result)

    # In a real app you would call your own LLM here and pass the response text.
    output_result = guard_output("LLM response here", session_id=input_result["session_id"])
    print("output:", output_result)

