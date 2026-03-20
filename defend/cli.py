from __future__ import annotations

import asyncio
import json
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

    config_path = Path("defend.config.yaml")
    if not config_path.exists():
        typer.echo(
            "Missing `defend.config.yaml` in the project root.\n"
            "Run `defend init` to generate it.",
            err=True,
        )
        raise typer.Exit(code=1)

    uvicorn.run("defend_api.main:app", host=host, port=port, log_level=log_level)


def _csv_list(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p]


def _prompt_modules(direction: str, allow_custom: bool) -> list[Any]:
    if direction not in {"input", "output"}:
        raise typer.BadParameter("direction must be input or output")

    # Direction selection mirrors runtime:
    # - input chain uses direction "input" or "both"
    # - output chain uses direction "output" or "both"
    allowed_dirs = {"input", "both"} if direction == "input" else {"output", "both"}

    # Dynamically list modules from the repo registry so the CLI supports new modules.
    try:
        from defend_api.modules import get_active_modules  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        raise typer.Exit(code=1) from exc

    custom_name = "custom" if direction == "input" else "custom_output"

    active = get_active_modules()
    available = [
        name
        for name, cls in active.items()
        if getattr(cls, "direction", "input") in allowed_dirs and (allow_custom or name != custom_name)
    ]
    available.sort()

    preview = ", ".join(available[:20]) + (", ..." if len(available) > 20 else "")
    raw = typer.prompt(
        f"Choose {direction} modules (comma-separated). Available: {preview}. Leave empty for none",
        default="",
        show_default=False,
    )
    selected = set(_csv_list(raw))

    unknown = sorted([name for name in selected if name not in set(available)])
    if unknown:
        raise typer.BadParameter(f"Unknown {direction} module(s): {', '.join(unknown)}")

    import yaml  # type: ignore

    out: list[Any] = []
    for name in sorted(selected):
        # Convenience prompts for the two common modules that need structured inputs.
        if name in {"topic", "topic_output"}:
            topics_raw = typer.prompt("Allowed topics (comma-separated)", default="", show_default=False)
            allowed_topics = _csv_list(topics_raw)
            out.append({name: {"allowed_topics": allowed_topics}})
            continue

        if name in {"custom", "custom_output"}:
            prompt = typer.prompt(f"{name} prompt (plain language rule)")
            out.append({name: {"prompt": prompt}})
            continue

        # For all other modules, accept arbitrary YAML/JSON config mapping.
        config_raw = typer.prompt(
            f"Config for module '{name}' as YAML/JSON mapping (empty = none)",
            default="",
            show_default=False,
        )
        if not config_raw.strip():
            out.append(name)
            continue

        parsed = yaml.safe_load(config_raw)
        if parsed is None or parsed == {}:
            out.append(name)
            continue
        if not isinstance(parsed, dict):
            raise typer.BadParameter(f"Config for '{name}' must parse to a YAML/JSON mapping/object.")

        out.append({name: parsed})

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

    llm_selected = primary in {"openai", "claude"}
    input_modules: list[Any] = []
    if llm_selected:
        if primary == "openai":
            models["openai"] = typer.prompt("OpenAI model id", default="gpt-4o-mini")
        if primary == "claude":
            models["claude"] = typer.prompt("Claude model id", default="claude-3-5-haiku-latest")

        input_modules = _prompt_modules("input", allow_custom=True)

    output_enabled = typer.confirm("Enable output guard?", default=llm_selected)
    output_modules: list[Any] = []
    output_provider = "claude"

    if output_enabled:
        output_provider = (
            typer.prompt(
                "Output guard provider (claude or openai)",
                default=("openai" if primary == "openai" else "claude"),
            )
            .strip()
            .lower()
        )
        if output_provider not in {"claude", "openai"}:
            raise typer.BadParameter("Output guard provider must be 'claude' or 'openai'")

        # Ensure we prompt for the model if this provider wasn't already selected as primary.
        if output_provider == "openai" and "openai" not in models:
            models["openai"] = typer.prompt("OpenAI model id", default="gpt-4o-mini")
        if output_provider == "claude" and "claude" not in models:
            models["claude"] = typer.prompt("Claude model id", default="claude-3-5-haiku-latest")

        output_modules = _prompt_modules("output", allow_custom=True)

    payload: Dict[str, Any] = {
        "v": 1,
        "providers": {
            "primary": primary,
        },
        "models": models,
        "modules": input_modules,
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


@app.command()
def test(
    text: Optional[str] = typer.Argument(
        None,
        help="Text to test. If neither --input nor --output is provided, this defaults to --input.",
    ),
    input_text: Optional[str] = typer.Option(
        None,
        "--input",
        help="Run the input guard on this text.",
    ),
    output_text: Optional[str] = typer.Option(
        None,
        "--output",
        help="Run the output guard on this text.",
    ),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        help="Optional session_id to link input and output guards.",
    ),
    pretty: bool = typer.Option(
        True,
        "--pretty/--no-pretty",
        help="Pretty-print JSON output.",
    ),
) -> None:
    """
    Test guard input/output via the CLI.

    Examples:
      defend test "Tell me how to bypass controls."
      defend test --input "..."
      defend test --output "LLM response" --session-id def-...
    """
    if text is not None and (input_text is not None or output_text is not None):
        raise typer.BadParameter("Provide either positional TEXT or --input/--output (not both).")

    if input_text is None and output_text is None:
        if text is None:
            raise typer.BadParameter('Provide TEXT or one of `--input` / `--output`.')
        input_text = text

    if input_text is not None and output_text is not None:
        # Full chain in one run.
        async def _run_both() -> tuple[dict[str, Any], dict[str, Any]]:
            from defend_api.routers.guard import guard_input, guard_output
            from defend_api.schemas import GuardInputRequest, GuardOutputRequest

            in_req = GuardInputRequest(text=input_text, session_id=session_id)
            in_resp = await guard_input(in_req)
            in_payload: dict[str, Any] = json.loads(in_resp.body.decode("utf-8"))
            linked_session_id = in_payload.get("session_id") or session_id

            out_req = GuardOutputRequest(text=output_text, session_id=linked_session_id)
            out_resp = await guard_output(out_req)
            out_payload: dict[str, Any] = json.loads(out_resp.body.decode("utf-8"))
            return in_payload, out_payload

        try:
            in_result, out_result = asyncio.run(_run_both())
        except KeyboardInterrupt:  # pragma: no cover
            raise typer.Exit(code=130)
        except Exception as exc:
            typer.echo(f"Test failed: {exc}", err=True)
            raise typer.Exit(code=1)

        if pretty:
            typer.echo("Input result:")
            typer.echo(json.dumps(in_result, indent=2, ensure_ascii=False))
            typer.echo("\nOutput result:")
            typer.echo(json.dumps(out_result, indent=2, ensure_ascii=False))
        else:
            typer.echo("input_result=" + json.dumps(in_result, ensure_ascii=False))
            typer.echo("output_result=" + json.dumps(out_result, ensure_ascii=False))
        return

    async def _run_one() -> dict[str, Any]:
        from defend_api.routers.guard import guard_input, guard_output
        from defend_api.schemas import GuardInputRequest, GuardOutputRequest

        if input_text is not None:
            req = GuardInputRequest(text=input_text, session_id=session_id)
            resp = await guard_input(req)
        else:
            req = GuardOutputRequest(text=output_text or "", session_id=session_id)
            resp = await guard_output(req)

        return json.loads(resp.body.decode("utf-8"))

    try:
        result = asyncio.run(_run_one())
    except KeyboardInterrupt:  # pragma: no cover
        raise typer.Exit(code=130)
    except Exception as exc:
        typer.echo(f"Test failed: {exc}", err=True)
        raise typer.Exit(code=1)

    if pretty:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        typer.echo(json.dumps(result, ensure_ascii=False))

