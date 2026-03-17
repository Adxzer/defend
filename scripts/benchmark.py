from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import math
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional, Sequence, Tuple


DatasetKey = Literal["deepset"]
ModelKey = Literal["defend_api"]
SubsetKey = Literal["overall", "en", "non_en", "ar", "zh", "ru", "fa", "es", "fr"]


TARGET_LANGS: Tuple[SubsetKey, ...] = ("ar", "zh", "ru", "fa", "es", "fr")
ALL_SUBSETS: Tuple[SubsetKey, ...] = ("overall", "en", "non_en", *TARGET_LANGS)


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _stable_id(parts: Sequence[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def _safe_preview(text: str, max_len: int = 160) -> str:
    t = " ".join(text.split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _as_bool_label(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return bool(int(value))
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "t", "yes", "y", "inj", "injection", "attack", "malicious", "jailbreak"}:
            return True
        if v in {"0", "false", "f", "no", "n", "benign", "clean", "safe", "neutral"}:
            return False
    return None


def _pick_text(row: Dict[str, Any]) -> Optional[str]:
    candidates = [
        "text",
        "prompt",
        "injection_prompt",
        "user_input",
        "input",
        "instruction",
        "query",
        "content",
        "sample",
        "jailbreak",
        "attack",
        "payload",
    ]
    for k in candidates:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v

    for v in row.values():
        if isinstance(v, str) and v.strip():
            return v
    return None


def _dataset_name(key: DatasetKey) -> str:
    if key == "deepset":
        return "deepset/prompt-injections"
    raise ValueError(f"Unknown dataset key: {key}")


def _require(extra: str, exc: Exception) -> None:
    msg = (
        f"Missing optional dependency. Install with `pip install defend[{extra}]` "
        f"or add the dependency to your environment.\n\nOriginal error: {exc}"
    )
    raise RuntimeError(msg) from exc


@dataclass(frozen=True)
class Sample:
    sample_id: str
    text: str
    label_is_injection: Optional[bool]
    lang: Optional[str] = None
    meta: Dict[str, Any] = dataclasses.field(default_factory=dict)


def _load_hf_dataset_all_splits(dataset_key: DatasetKey) -> Tuple[str, Any]:
    try:
        from datasets import concatenate_datasets, load_dataset  # type: ignore
    except Exception as exc:
        _require("benchmark", exc)

    name = _dataset_name(dataset_key)
    ds_obj = load_dataset(name)  # type: ignore
    if hasattr(ds_obj, "keys"):
        splits = []
        for split_name in list(ds_obj.keys()):
            splits.append(ds_obj[split_name])
        if not splits:
            raise RuntimeError(f"No splits found for dataset {name}")
        if len(splits) == 1:
            return name, splits[0]
        return name, concatenate_datasets(splits)  # type: ignore

    return name, ds_obj


def _normalize_samples(dataset_key: DatasetKey, hf_dataset: Any, *, limit: Optional[int]) -> List[Sample]:
    samples: List[Sample] = []
    n = 0
    for idx, row in enumerate(hf_dataset):
        if limit is not None and n >= limit:
            break
        if not isinstance(row, dict):
            continue
        text = _pick_text(row)
        if not isinstance(text, str) or not text.strip():
            continue

        label_val = row.get("label")
        if label_val is None:
            label_val = row.get("is_injection")
        label = _as_bool_label(label_val)

        sid = _stable_id([dataset_key, str(idx), text[:256]])
        samples.append(
            Sample(
                sample_id=sid,
                text=text,
                label_is_injection=label,
                lang=None,
                meta={"row_index": idx},
            )
        )
        n += 1
    return samples


def _init_langdetect(seed: int) -> None:
    try:
        from langdetect import DetectorFactory  # type: ignore
    except Exception as exc:
        _require("benchmark", exc)
    DetectorFactory.seed = seed


def _detect_lang(samples: List[Sample]) -> List[Sample]:
    try:
        from langdetect import detect  # type: ignore
    except Exception as exc:
        _require("benchmark", exc)

    out: List[Sample] = []
    cache: Dict[str, Optional[str]] = {}
    for s in samples:
        if s.sample_id in cache:
            out.append(dataclasses.replace(s, lang=cache[s.sample_id]))
            continue
        lang: Optional[str]
        try:
            lang = detect(s.text)
        except Exception:
            lang = None
        cache[s.sample_id] = lang
        out.append(dataclasses.replace(s, lang=lang))
    return out


def _subset_samples(
    samples: List[Sample],
    *,
    seed: int,
    target_languages: Sequence[SubsetKey],
    per_lang_target_n: int = 100,
) -> Dict[SubsetKey, List[Sample]]:
    rng = random.Random(seed)
    by_lang: Dict[str, List[Sample]] = {}
    for s in samples:
        if s.lang:
            by_lang.setdefault(s.lang, []).append(s)

    subsets: Dict[SubsetKey, List[Sample]] = {}
    subsets["overall"] = list(samples)
    subsets["en"] = list(by_lang.get("en", []))
    subsets["non_en"] = [s for s in samples if (s.lang is not None and s.lang != "en")]

    for lang in target_languages:
        if lang in {"overall", "en", "non_en"}:
            continue
        pool = list(by_lang.get(lang, []))
        if len(pool) <= per_lang_target_n:
            subsets[lang] = pool
        else:
            subsets[lang] = rng.sample(pool, k=per_lang_target_n)

    return subsets


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    fn: int
    tn: int


def _confusion(y_true: Sequence[bool], y_pred: Sequence[bool]) -> Confusion:
    tp = fp = fn = tn = 0
    for t, p in zip(y_true, y_pred):
        if p and t:
            tp += 1
        elif p and not t:
            fp += 1
        elif (not p) and t:
            fn += 1
        else:
            tn += 1
    return Confusion(tp=tp, fp=fp, fn=fn, tn=tn)


def _precision_recall_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _fpr(fp: int, tn: int) -> float:
    return fp / (fp + tn) if (fp + tn) else 0.0


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


def _latency_summary_ms(latencies_ms: Sequence[float]) -> Dict[str, float]:
    vals = sorted(float(x) for x in latencies_ms if x is not None and math.isfinite(float(x)))
    return {
        "p50": _percentile(vals, 50),
        "p95": _percentile(vals, 95),
        "p99": _percentile(vals, 99),
    }


async def _defend_api_predict_many(
    *,
    base_url: str,
    api_key: str,
    texts: Sequence[str],
    concurrency: int,
    timeout_s: float,
) -> Tuple[List[bool], List[float], List[Dict[str, Any]]]:
    try:
        import httpx  # type: ignore
    except Exception as exc:
        _require("benchmark", exc)

    sem = asyncio.Semaphore(concurrency)
    preds: List[Optional[bool]] = [None] * len(texts)
    lats: List[Optional[float]] = [None] * len(texts)
    raw: List[Optional[Dict[str, Any]]] = [None] * len(texts)

    headers: Dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=headers,
        timeout=timeout_s,
    ) as client:

        async def one(i: int, text: str) -> None:
            async with sem:
                body = {"text": text, "session_id": None, "metadata": {}}
                start = time.perf_counter()
                resp = await client.post("/guard/input", json=body)
                data = resp.json()
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                action = str(data.get("action", "")).lower()
                preds[i] = action in {"block", "flag"}
                lats[i] = elapsed_ms
                raw[i] = data

        await asyncio.gather(*(one(i, t) for i, t in enumerate(texts)))

    return (
        [bool(x) for x in preds],
        [float(x) if x is not None else float("nan") for x in lats],
        [x if x is not None else {} for x in raw],
    )


async def _defend_api_latency_benchmark(
    *,
    base_url: str,
    api_key: str,
    texts: Sequence[str],
    concurrency: int,
    timeout_s: float,
    warmup_n: int = 100,
    timed_n: int = 500,
) -> Dict[str, Any]:
    if not texts:
        raise RuntimeError("No texts provided for latency benchmarking.")

    # Warmup (not recorded)
    warmup_texts = [texts[i % len(texts)] for i in range(warmup_n)]
    await _defend_api_predict_many(
        base_url=base_url,
        api_key=api_key,
        texts=warmup_texts,
        concurrency=concurrency,
        timeout_s=timeout_s,
    )

    timed_texts = [texts[i % len(texts)] for i in range(timed_n)]
    _, lats, _ = await _defend_api_predict_many(
        base_url=base_url,
        api_key=api_key,
        texts=timed_texts,
        concurrency=concurrency,
        timeout_s=timeout_s,
    )
    summary = _latency_summary_ms(lats)
    return {
        "warmup_n": warmup_n,
        "timed_n": timed_n,
        "latencies_ms": lats,
        "summary_ms": summary,
    }


def _env_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }
    return info


def _pkg_versions() -> Dict[str, Optional[str]]:
    try:
        import importlib.metadata as importlib_metadata  # py3.8+
    except Exception:  # pragma: no cover
        return {}
    pkgs = ["defend", "httpx", "datasets", "langdetect"]
    out: Dict[str, Optional[str]] = {}
    for p in pkgs:
        try:
            out[p] = importlib_metadata.version(p)
        except Exception:
            out[p] = None
    return out


def _gpu_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"has_cuda": False, "cuda_device_name": None}
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            info["has_cuda"] = True
            try:
                info["cuda_device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                info["cuda_device_name"] = "unknown"
    except Exception:
        # Keep defaults when torch is not installed.
        pass
    return info


def _best_effort_git_sha(repo_root: Path) -> Optional[str]:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return None
        sha = (res.stdout or "").strip()
        return sha or None
    except Exception:
        return None


def _format_float(x: Optional[float], digits: int = 3) -> str:
    if x is None:
        return "—"
    if not math.isfinite(float(x)):
        return "—"
    return f"{float(x):.{digits}f}"


def _format_ms(x: Optional[float]) -> str:
    if x is None:
        return "—"
    if not math.isfinite(float(x)):
        return "—"
    return f"{float(x):.1f}"


def _print_markdown_table(rows: List[Dict[str, Any]]) -> None:
    headers = [
        "dataset",
        "model",
        "subset",
        "n",
        "precision",
        "recall",
        "f1",
        "fpr",
        "p50_ms",
        "p95_ms",
        "p99_ms",
    ]
    print()
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        vals = [str(r.get(h, "")) for h in headers]
        print("| " + " | ".join(vals) + " |")


def _parse_languages_flag(arg: str) -> List[SubsetKey]:
    raw = [a.strip() for a in (arg or "").split(",") if a.strip()]
    if not raw or raw == ["all"]:
        return list(ALL_SUBSETS)
    out: List[SubsetKey] = []
    for x in raw:
        if x not in ALL_SUBSETS:
            raise ValueError(f"Unknown language subset: {x}. Allowed: {', '.join(ALL_SUBSETS)}")
        out.append(x)  # type: ignore[arg-type]
    return out


async def main_async(args: argparse.Namespace) -> int:
    seed: int = int(args.seed)
    random.seed(seed)
    try:
        import numpy as np  # type: ignore

        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch  # type: ignore

        torch.manual_seed(seed)
    except Exception:
        pass

    _init_langdetect(seed)

    datasets_to_run: List[DatasetKey] = ["deepset"]
    models_to_run: List[ModelKey] = ["defend_api"]
    subsets_to_run: List[SubsetKey] = _parse_languages_flag(args.languages)

    repo_root = Path(__file__).resolve().parents[1]
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    run_meta: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "args": {
            "model": args.model,
            "dataset": args.dataset,
            "languages": args.languages,
            "limit": args.limit,
            "outdir": str(outdir),
        },
        "env": _env_info(),
        "gpu": _gpu_info(),
        "package_versions": _pkg_versions(),
        "git_sha": _best_effort_git_sha(repo_root),
    }

    results: Dict[str, Any] = {"meta": run_meta, "datasets": {}, "runs": []}
    table_rows: List[Dict[str, Any]] = []

    for dkey in datasets_to_run:
        hf_name, hf_ds = _load_hf_dataset_all_splits(dkey)
        base_samples = _normalize_samples(dkey, hf_ds, limit=args.limit)
        samples = _detect_lang(base_samples)
        subsets = _subset_samples(
            samples,
            seed=seed,
            target_languages=[s for s in subsets_to_run if s in TARGET_LANGS],
            per_lang_target_n=max(100, int(args.per_lang_n)),
        )
        # Ensure requested subsets exist
        for s in ("overall", "en", "non_en"):
            if s in subsets_to_run and s not in subsets:
                subsets[s] = []

        results["datasets"][dkey] = {
            "hf_name": hf_name,
            "n_total": len(samples),
            "n_by_subset": {k: len(v) for k, v in subsets.items()},
        }

        # Prepare a deterministic pool of texts for latency benchmarking per dataset.
        latency_pool = [s.text for s in subsets.get("overall", []) if isinstance(s.text, str)]
        if not latency_pool:
            latency_pool = [s.text for s in samples[:100] if isinstance(s.text, str)]

        for mkey in models_to_run:
            base_url = str(args.base_url).rstrip("/")
            if base_url.endswith("/v1"):
                base_url_v1 = base_url
            else:
                base_url_v1 = base_url + "/v1"

            latency_block = await _defend_api_latency_benchmark(
                base_url=base_url_v1,
                api_key=str(args.api_key),
                texts=latency_pool,
                concurrency=int(args.concurrency),
                timeout_s=float(args.timeout_s),
                warmup_n=100,
                timed_n=500,
            )

            for subset_key in subsets_to_run:
                subset_samples = subsets.get(subset_key, [])
                # Keep evaluation bounded and deterministic if subset is huge.
                eval_samples = subset_samples
                if args.eval_limit is not None and len(eval_samples) > int(args.eval_limit):
                    rng = random.Random(seed + 17)
                    eval_samples = rng.sample(eval_samples, k=int(args.eval_limit))

                texts = [s.text for s in eval_samples]
                y_true_opt = [s.label_is_injection for s in eval_samples]
                # Skip rows we cannot label (only relevant for deepset)
                filtered: List[Tuple[str, bool]] = []
                filtered_ids: List[str] = []
                for s, lab in zip(eval_samples, y_true_opt):
                    if lab is None:
                        continue
                    filtered.append((s.text, bool(lab)))
                    filtered_ids.append(s.sample_id)

                if not filtered:
                    continue
                texts_f = [t for t, _ in filtered]
                y_true = [lab for _, lab in filtered]

                base_url = str(args.base_url).rstrip("/")
                base_url_v1 = base_url if base_url.endswith("/v1") else (base_url + "/v1")
                y_pred, eval_lats, raw = await _defend_api_predict_many(
                    base_url=base_url_v1,
                    api_key=str(args.api_key),
                    texts=texts_f,
                    concurrency=int(args.concurrency),
                    timeout_s=float(args.timeout_s),
                )
                raw_preds = [
                    {
                        "sample_id": sid,
                        "text_preview": _safe_preview(text),
                        "y_true": yt,
                        "y_pred": yp,
                        "latency_ms": lat,
                        "raw": r,
                    }
                    for sid, text, yt, yp, lat, r in zip(filtered_ids, texts_f, y_true, y_pred, eval_lats, raw)
                ]

                confusion = _confusion(y_true, y_pred)
                precision, recall, f1 = _precision_recall_f1(confusion.tp, confusion.fp, confusion.fn)
                fpr = _fpr(confusion.fp, confusion.tn)

                precision_out = precision
                f1_out = f1
                fpr_out = fpr

                eval_lat_summary = _latency_summary_ms(eval_lats)

                run_block = {
                    "dataset": dkey,
                    "model": mkey,
                    "subset": subset_key,
                    "n": len(y_true),
                    "confusion": dataclasses.asdict(confusion),
                    "metrics": {
                        "precision": precision_out,
                        "recall": recall,
                        "f1": f1_out,
                        "fpr": fpr_out,
                        "fnr": None,
                    },
                    "eval_latency_ms": {
                        "summary_ms": eval_lat_summary,
                        "latencies_ms": eval_lats,
                    },
                    "latency_benchmark": latency_block,
                    "predictions": raw_preds,
                }
                results["runs"].append(run_block)

                table_rows.append(
                    {
                        "dataset": dkey,
                        "model": mkey,
                        "subset": subset_key,
                        "n": len(y_true),
                        "precision": _format_float(precision_out),
                        "recall": _format_float(recall),
                        "f1": _format_float(f1_out),
                        "fpr": _format_float(fpr_out),
                        "p50_ms": _format_ms(eval_lat_summary["p50"]),
                        "p95_ms": _format_ms(eval_lat_summary["p95"]),
                        "p99_ms": _format_ms(eval_lat_summary["p99"]),
                    }
                )

    ts = _now_ts()
    out_path = outdir / f"results_{ts}.json"
    latest_path = outdir / "latest.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    shutil.copyfile(out_path, latest_path)

    _print_markdown_table(table_rows)
    print()
    print(f"Wrote: {out_path}")
    print(f"Latest: {latest_path}")
    return 0


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DEFEND benchmark suite (publishable metrics + latency).")
    p.add_argument("--model", choices=["defend_api"], default="defend_api", help="Only supported model.")
    p.add_argument("--dataset", choices=["deepset"], default="deepset", help="Only supported dataset.")
    p.add_argument(
        "--languages",
        default="all",
        help="Comma-separated subsets: all,en,non_en,ar,zh,ru,fa,es,fr",
    )
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--limit", type=int, default=None, help="Max HF rows to load per dataset (before language slicing).")
    p.add_argument("--eval-limit", type=int, default=None, help="Cap evaluation rows per subset (after slicing).")
    p.add_argument("--per-lang-n", type=int, default=100, help="Target sample size per target language (when available).")
    p.add_argument("--outdir", default="benchmarks", help="Output directory for JSON results.")

    p.add_argument("--base-url", default=os.environ.get("DEFEND_BASE_URL", "http://localhost:8000"))
    p.add_argument("--api-key", default=os.environ.get("DEFEND_API_KEY", ""))
    p.add_argument("--concurrency", type=int, default=25)
    p.add_argument("--timeout-s", type=float, default=30.0)
    return p


def main() -> int:
    args = build_argparser().parse_args()
    if args.model in {"defend_api", "all"} and not str(args.api_key):
        # The current server may not enforce auth, but the client sends it for forward-compat.
        print("Warning: DEFEND_API_KEY is empty; requests will still include an Authorization header.")
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

