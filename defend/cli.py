from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import typer

from .init_token import (
    InitTokenError,
    decode_init_token,
    defend_config_dict_to_payload,
    encode_init_token,
    payload_to_defend_config_dict,
)

app = typer.Typer(add_completion=False, help="Defend CLI")


def _require(exc: Exception) -> None:
    typer.echo(
        (
            "Missing runtime dependency. Install with `pip install pydefend` "
            f"or add the dependency to your environment.\n\nOriginal error: {exc}"
        ),
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, log_level: str = "info") -> None:
    """
    Start the Defend server (FastAPI) via uvicorn.
    """
    try:
        import uvicorn  # type: ignore
    except Exception as exc:  # pragma: no cover
        _require(exc)

    try:
        import defend_api.main  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover
        _require(exc)

    uvicorn.run("defend_api.main:app", host=host, port=port, log_level=log_level)


def _csv_list(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p]


def _prompt_modules(direction: str, allow_custom: bool) -> list[Any]:
    if direction not in {"input", "output"}:
        raise typer.BadParameter("direction must be input or output")

    if direction == "input":
        builtin = ["injection", "pii", "topic"]
        custom_name = "custom"
    else:
        builtin = ["prompt_leak", "pii_output", "topic_output"]
        custom_name = "custom_output"

    choices = ", ".join(builtin + ([custom_name] if allow_custom else []))
    raw = typer.prompt(
        f"Choose {direction} modules (comma-separated). Available: {choices}. Leave empty for none",
        default="",
        show_default=False,
    )
    selected = set(_csv_list(raw))

    out: list[Any] = []
    for name in builtin:
        if name in selected:
            if name in {"topic", "topic_output"}:
                topics_raw = typer.prompt("Allowed topics (comma-separated)", default="", show_default=False)
                allowed_topics = _csv_list(topics_raw)
                out.append({name: {"allowed_topics": allowed_topics}})
            else:
                out.append(name)

    if allow_custom and custom_name in selected:
        prompt = typer.prompt(f"{custom_name} prompt (plain language rule)")
        out.append({custom_name: {"prompt": prompt}})

    return out


@app.command()
def init(
    token: Optional[str] = typer.Option(None, "--token", help="Init token string (defend_v1_...)"),
    from_config: bool = typer.Option(False, "--from-config", help="Export token from existing defend.config.yaml"),
    out_path: str = typer.Option("defend.config.yaml", "--out", help="Where to write the generated config"),
) -> None:
    """
    Initialize Defend quickly from a compressed token, export a token, or run an interactive wizard.
    """
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        typer.echo(
            "Missing dependency: PyYAML is required for `defend init`. Install with `pip install pyyaml`.",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    if from_config:
        try:
            raw = yaml.safe_load(Path("defend.config.yaml").read_text(encoding="utf-8")) or {}
        except Exception as exc:
            typer.echo(f"Failed to read defend.config.yaml: {exc}", err=True)
            raise typer.Exit(code=1)
        if not isinstance(raw, dict):
            typer.echo("defend.config.yaml must contain a YAML mapping at the top level", err=True)
            raise typer.Exit(code=1)
        payload = defend_config_dict_to_payload(raw)
        typer.echo(encode_init_token(payload))
        return

    if token:
        try:
            payload = decode_init_token(token)
        except InitTokenError as exc:
            typer.echo(f"Invalid init token: {exc}", err=True)
            raise typer.Exit(code=1)

        cfg = payload_to_defend_config_dict(payload)

        try:
            from defend_api.config import DefendConfig  # type: ignore

            DefendConfig.model_validate(cfg)
        except Exception:
            pass

        try:
            Path(out_path).write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        except Exception as exc:
            typer.echo(f"Failed to write {out_path}: {exc}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Wrote {out_path}")
        return

    primary = typer.prompt("Choose primary provider (defend, openai, claude)", default="defend").strip().lower()
    if primary not in {"defend", "openai", "claude"}:
        raise typer.BadParameter("Primary provider must be one of: defend, openai, claude")

    models: Dict[str, str] = {}
    if primary == "openai":
        models["openai"] = typer.prompt("OpenAI model id", default="gpt-4.1-mini")
    if primary == "claude":
        models["claude"] = typer.prompt("Claude model id", default="claude-3-5-sonnet-20241022")

    llm_selected = primary in {"openai", "claude"}
    input_modules = _prompt_modules("input", allow_custom=llm_selected)
    output_enabled = llm_selected and typer.confirm("Enable output guard?", default=True)
    output_modules: list[Any] = []
    output_provider = "claude" if primary != "openai" else "openai"
    if output_enabled:
        output_modules = _prompt_modules("output", allow_custom=True)

    payload: Dict[str, Any] = {
        "v": 1,
        "providers": {
            "primary": primary,
        },
        "models": models,
        "modules": [],
        "guards": {
            "input": {"provider": primary, "modules": input_modules},
            "output": {
                "enabled": bool(output_enabled),
                "provider": output_provider,
                "modules": output_modules,
                "on_fail": "block",
            },
            "session_ttl_seconds": 300,
        },
    }

    token_out = encode_init_token(payload)
    typer.echo("\nInit token:\n" + token_out + "\n")

    cfg = payload_to_defend_config_dict(payload)
    try:
        Path(out_path).write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    except Exception as exc:
        typer.echo(f"Failed to write {out_path}: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Wrote {out_path}")

