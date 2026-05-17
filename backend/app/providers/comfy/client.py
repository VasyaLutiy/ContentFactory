from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request

from app.core.config import get_settings


class ComfyClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ComfyPromptResponse:
    prompt_id: str
    node_errors: dict[str, Any]


class ComfyClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.base_url = (base_url or get_settings().comfy_url).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_object_info(self) -> dict[str, Any]:
        return self._json_request("GET", "/object_info")

    def get_queue(self) -> dict[str, Any]:
        return self._json_request("GET", "/queue")

    def get_history(self, prompt_id: str) -> dict[str, Any]:
        return self._json_request("GET", f"/history/{prompt_id}")

    def queue_prompt(self, workflow: dict[str, Any], client_id: str) -> ComfyPromptResponse:
        payload = {"prompt": workflow, "client_id": client_id}
        data = self._json_request("POST", "/prompt", payload)
        prompt_id = data.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyClientError("ComfyUI response did not include prompt_id.")
        node_errors = data.get("node_errors") or {}
        if not isinstance(node_errors, dict):
            node_errors = {"raw": node_errors}
        return ComfyPromptResponse(prompt_id=prompt_id, node_errors=node_errors)

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.URLError as exc:
            raise ComfyClientError(f"ComfyUI request failed: {exc}") from exc

        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComfyClientError("ComfyUI returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise ComfyClientError("ComfyUI returned a non-object JSON response.")
        return decoded
