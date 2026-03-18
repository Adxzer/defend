from __future__ import annotations

from pathlib import Path
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple

import typer

from .client import Client
from .exceptions import DefendError
from .init_token import (
    InitTokenError,
    decode_init_token,
    defend_config_dict_to_payload,
    encode_init_token,
    payload_to_defend_config_dict,
)

app = typer.Typer(add_completion=False, help="Defend CLI")


def _require(extra: str, exc: Exception) -> None:
    typer.echo(
        (
            f"Missing optional dependency. Install with `pip install defend[{extra}]` "
            f"or add the dependency to your environment.\n\nOriginal error: {exc}"
        ),
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, log_level: str = "info") -> None:
    """
    Start the Defend server (FastAPI) via uvicorn.

    Requires `defend[server]` to be installed.
    """

    try:
        import uvicorn  # type: ignore
    except Exception as exc:  # pragma: no cover
        _require("server", exc)

    # Import lazily so base `pip install defend` stays lightweight.
    try:
        import defend.api.main  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover
        _require("server", exc)

    # Use the unified `defend.api.main:app` entrypoint.
    uvicorn.run("defend.api.main:app", host=host, port=port, log_level=log_level)


@app.command()
def test(
    api_key: str = typer.Option(..., envvar="DEFEND_API_KEY", help="Defend API key"),
    base_url: str = typer.Option("http://localhost:8000", envvar="DEFEND_BASE_URL", help="Server base URL"),
) -> None:
    """
    Run a built-in smoke test suite against a running Defend instance.
    """

    client = Client(api_key=api_key, base_url=base_url)
    try:
        health = client.health()
        typer.echo(f"health: {health.status} (providers={len(health.providers)})")

        res_in = client.input("Hello world")
        typer.echo(f"guard.input: action={res_in.action} session_id={res_in.session_id}")

        # Output guarding may require non-defend provider configured server-side; treat errors as informative.
        try:
            res_out = client.output("This is a harmless response.", session_id=res_in.session_id)
            typer.echo(f"guard.output: action={res_out.action} context={res_out.context}")
        except DefendError as exc:
            typer.echo(f"guard.output: skipped/failed ({exc})")

        sess = client.get_session(res_in.session_id)
        typer.echo(f"session: turns={sess.turns} risk_score={sess.risk_score} peak_score={sess.peak_score}")

        client.delete_session(res_in.session_id)
        typer.echo("session: deleted")
    finally:
        client.close()


def _precision_recall_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


@app.command()
def benchmark(
    api_key: str = typer.Option(..., envvar="DEFEND_API_KEY", help="Defend API key"),
    base_url: str = typer.Option("http://localhost:8000", envvar="DEFEND_BASE_URL", help="Server base URL"),
    limit: int = typer.Option(200, help="Max samples to evaluate"),
) -> None:
    """
    Run a small benchmark against the deepset/prompt-injections dataset.

    Requires `defend[benchmark]` (and a running server).
    """

    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:  # pragma: no cover
        _require("benchmark", exc)

    ds = load_dataset("deepset/prompt-injections", split="test")  # type: ignore

    client = Client(api_key=api_key, base_url=base_url)
    latencies_ms: List[float] = []
    tp = fp = fn = tn = 0

    try:
        for i, row in enumerate(ds):
            if i >= limit:
                break

            text = row.get("text") or row.get("prompt") or row.get("injection_prompt")  # dataset variants
            label = row.get("label") or row.get("is_injection")
            if not isinstance(text, str) or label is None:
                continue

            # Normalize label to bool: True means injection.
            is_injection = bool(label)

            start = time.perf_counter()
            result = client.input(text)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies_ms.append(elapsed_ms)

            pred_injection = result.action in ("block", "flag")

            if pred_injection and is_injection:
                tp += 1
            elif pred_injection and not is_injection:
                fp += 1
            elif (not pred_injection) and is_injection:
                fn += 1
            else:
                tn += 1

        precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
        p50 = statistics.median(latencies_ms) if latencies_ms else 0.0
        p95 = statistics.quantiles(latencies_ms, n=20)[18] if len(latencies_ms) >= 20 else p50

        typer.echo(f"samples={tp+fp+fn+tn} tp={tp} fp={fp} fn={fn} tn={tn}")
        typer.echo(f"precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}")
        typer.echo(f"latency_ms: p50={p50:.1f} p95={p95:.1f}")
    finally:
        client.close()


def _csv_list(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",")]
    return [p for p in parts if p]


def _prompt_modules(direction: str, allow_custom: bool) -> list[Any]:
    """
    Prompt for module selection.

    Returns a list of module specs compatible with `build_modules_from_specs`, e.g.:
    - "pii"
    - {"topic": {"allowed_topics": ["..."]}}
    - {"custom": {"prompt": "..."}}
    """
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


def _select_provider_chain(selected: set[str]) -> dict[str, Any]:
    """
    Backwards compatibility shim for older versions.

    Fallback/chaining has been removed; pick a single primary provider.
    """
    if not selected:
        return {"primary": "defend"}
    if len(selected) == 1:
        return {"primary": next(iter(selected))}
    # If multiple were provided, prefer defend if present, otherwise prefer openai.
    if "defend" in selected:
        return {"primary": "defend"}
    if "openai" in selected:
        return {"primary": "openai"}
    return {"primary": "claude"}


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

        # Best-effort validation if server deps are present.
        try:
            from defend.api.config import DefendConfig  # type: ignore

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

    # Interactive wizard
    primary = typer.prompt("Choose primary provider (defend, openai, claude)", default="defend").strip().lower()
    if primary not in {"defend", "openai", "claude"}:
        raise typer.BadParameter("Primary provider must be one of: defend, openai, claude")
    provider_cfg = {"primary": primary}

    models: dict[str, str] = {}
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
            "primary": provider_cfg.get("primary", "defend"),
        },
        "models": models,
        "modules": [],
        "guards": {
            "input": {"provider": provider_cfg.get("primary", "defend"), "modules": input_modules},
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
