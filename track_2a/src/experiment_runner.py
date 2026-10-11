"""Cached-only paired v1.5 experiments; preflight never calls a model endpoint."""
import argparse
import ast
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse
import uuid

from booklet_app import (MLX_MODEL, MODEL, BookletRetriever, SubmissionJudge, build_messages,
                         classify, digest, evidence_payload, load_booklet, validate_request)
from config import EMBEDDING_MODEL, PROJECT_ROOT
from eval_nli import DEFAULT_DATA, load_rows, summarise
from eval_paired import coverage
from fetch_booklets import pdf_path
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION
from serve_experiments import REVISION, snapshot_info

SCHEMA = "hackapertus-experiments-v1"
PLAN = PROJECT_ROOT / "docs/evidence/paired_dev_plan_20261011.json"
OUTPUT = PROJECT_ROOT / "data/experiments/v15-paired"
ENCODER_REVISION = "7a91fa8a01af56c1f06060f7af3698ef5619e41c"


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_log(path):
    if not path.exists():
        return []
    data = path.read_bytes()
    records = []
    offset = 0
    for line in data.splitlines(keepends=True):
        try:
            records.append(json.loads(line))
        except (ValueError, UnicodeError):
            # Preserve the original bytes before repairing only an incomplete last write.
            if offset + len(line) != len(data) or line.endswith(b"\n"):
                raise ValueError("Corrupt result log; manual inspection required")
            backup = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
            backup.write_bytes(data)
            with path.open("r+b") as stream:
                stream.truncate(offset)
            return records
        offset += len(line)
    if data and not data.endswith(b"\n"):
        with path.open("ab") as stream:
            stream.write(b"\n")
    return records


@contextmanager
def locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".runner.lock"
    stream = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        stream.close()


def command(args, timeout=30, env=None):
    return subprocess.run(args, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=timeout)


def endpoint(value):
    url = urlparse(value)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Endpoint must be an HTTP(S) URL without embedded credentials or query parameters")
    return value.rstrip("/").removesuffix("/v1")


def output_path(path):
    path = path.resolve()
    root = (PROJECT_ROOT / "data/experiments").resolve()
    if path == root or root not in path.parents:
        raise ValueError("Use a run subdirectory under track_2a/data/experiments")
    path.mkdir(parents=True, exist_ok=True)
    with (path / (".write-check-" + uuid.uuid4().hex)).open("x") as stream:
        name = stream.name
    Path(name).unlink()
    return path


def static_checks():
    issues = []
    for name in ("README.md", "technical_report.md", "Dockerfile", "Makefile", "src", "data", "docs"):
        if not (PROJECT_ROOT / name).exists():
            issues.append("Missing template path: " + name)
    for path in (PROJECT_ROOT / "src").glob("*.py"):
        ast.parse(path.read_text(), filename=path.name)
    if not shutil.which("docker"):
        issues.append("Docker CLI/Compose missing (needed for submission only)")
    else:
        for files in (["compose.submission.yaml"], ["compose.submission.yaml", "compose.managed.yaml"]):
            argv = ["docker", "compose"]
            for file in files:
                argv += ["-f", file]
            proc = command(argv + ["config", "--format", "json"])
            if proc.returncode:
                issues.append("Compose configuration failed: " + ", ".join(files))
                continue
            config = json.loads(proc.stdout)
            app = config["services"]["app"]
            if app["environment"]["LLM_TOKEN_PREFLIGHT"] != "required":
                issues.append("Submission token preflight must be required")
            if len(files) == 1 and ("apertus" in config["services"] or app.get("depends_on") or app.get("deploy")):
                issues.append("External endpoint unexpectedly requires a model/GPU service")
    if shutil.which("make"):
        for mode in ("managed", "external"):
            if command(["make", "-n", "run", "SUBMISSION_MODE=" + mode]).returncode:
                issues.append("make run dry-run failed: " + mode)
    else:
        issues.append("GNU Make missing (needed for submission only)")
    request = json.loads((PROJECT_ROOT / "data/request.json").read_text())
    validate_request(request)
    return issues


def prepare(args):
    """Read and extract cached inputs only; no embeddings, model loading or HTTP."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    issues = []
    deployment = static_checks()
    versions = {}
    for name in ("requests", "numpy", "torch", "transformers", "huggingface-hub", "mlx-lm"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            issues.append("Missing dependency: " + name)
    if not shutil.which("pdftotext"):
        issues.append("Missing pdftotext")
    rows = load_rows(args.data)
    plan = json.loads(args.plan.read_text())
    if digest(args.data.read_bytes()) != plan["dataset_sha256"]:
        raise ValueError("Dataset hash differs from the verified plan")
    fixture = json.loads((PROJECT_ROOT / "tests/fixtures/paired_examples.json").read_text())
    if fixture["dataset_sha256"] != plan["dataset_sha256"] or any(
            rows[e["row_index"]] != e["row"] for e in fixture["examples"]):
        raise ValueError("Verified test examples differ from the dataset")
    indices = plan["plan"]["row_indices"]
    if not indices or len(indices) != len(set(indices)):
        raise ValueError("Empty or duplicate plan rows")
    booklets, items, pairs = {}, [], Counter()
    for index in indices:
        if type(index) is not int or not 0 <= index < len(rows):
            raise ValueError("Plan row outside dataset")
        row = rows[index]
        if type(row["entailment_label"]) is not int or row["entailment_label"] not in CODE_TO_LABEL:
            raise ValueError("Invalid gold label")
        request = {"claim": row["claim"], "claim_language": row["claim_language"],
                   "booklet": row["booklet_url"], "booklet_language": row["reference_language"]}
        validate_request(request)
        if not isinstance(row.get("reference_string"), str) or not row["reference_string"].strip():
            raise ValueError("Missing verified reference")
        if urlparse(request["booklet"]).scheme != "https":
            raise ValueError("Evaluation booklet must use the source HTTPS URL")
        key = (request["booklet"], request["booklet_language"])
        if key not in booklets:
            pdf = pdf_path(key[0])
            if not pdf.is_file():
                issues.append("Missing cached PDF for row " + str(index) + "; fetch-booklets manually")
                continue
            booklet = load_booklet(str(pdf), key[1])
            booklet["source"] = key[0]
            booklets[key] = booklet
        booklet = booklets[key]
        pairs[request["claim_language"] + "->" + request["booklet_language"]] += 1
        items.append({"row_index": index, "request": request, "gold": CODE_TO_LABEL[row["entailment_label"]],
                      "reference": row["reference_string"], "pdf_sha256": booklet["sha256"],
                      "extracted_text_sha256": fingerprint(booklet["pages"]),
                      "page_count": len(booklet["pages"])})
    if len(pairs) != 9:
        issues.append("Verified matrix does not cover all nine DE/FR/IT pairs")
    if dict(pairs) != plan["plan"]["language_pairs"]:
        issues.append("Language pairs differ from the verified plan")
    if dict(Counter(i["gold"] for i in items)) != {CODE_TO_LABEL[int(k)]: v for k, v in plan["plan"]["label_counts"].items()}:
        issues.append("Label counts differ from the verified plan")
    model_info, encoder = {}, None
    try:
        _, model_info = snapshot_info()
    except Exception as exc:
        issues.append("Cached MLX checkpoint unavailable or invalid: " + type(exc).__name__)
    try:
        from huggingface_hub import snapshot_download
        encoder = Path(snapshot_download(EMBEDDING_MODEL, revision=ENCODER_REVISION, local_files_only=True))
        if not (encoder / "config.json").is_file() or not (encoder / "tokenizer.json").is_file() or not any(encoder.glob("*.safetensors")):
            raise ValueError("Incomplete encoder snapshot")
        # Import smoke, not encoder construction or inference.
        import retriever  # noqa: F401
    except Exception as exc:
        issues.append("Cached encoder/import unavailable: " + type(exc).__name__)
    sources = {str(p.relative_to(PROJECT_ROOT)): digest(p.read_bytes())
               for p in sorted((PROJECT_ROOT / "src").glob("*.py"))}
    for name in ("Makefile", "Dockerfile", "compose.submission.yaml", "compose.managed.yaml", "requirements.txt",
                 "tests/fixtures/paired_examples.json"):
        sources[name] = digest((PROJECT_ROOT / name).read_bytes())
    revision = command(["git", "rev-parse", "HEAD"]).stdout.strip()
    dirty = bool(command(["git", "status", "--porcelain"]).stdout)
    config = {"backend": "native-mlx", "model": MLX_MODEL, "revision": REVISION,
              "endpoint": endpoint(args.endpoint), "context_tokens": args.context, "max_tokens": 512,
              "temperature": 0, "seed": 20261011, "top_k": 5, "token_preflight": "required",
              "chat_template_kwargs": {"enable_thinking": False}, "timeout_s": args.timeout,
              "retries": args.retries, "parser_version": LABEL_PARSE_VERSION,
              "encoder": EMBEDDING_MODEL, "encoder_revision": ENCODER_REVISION}
    contract = {"schema": SCHEMA, "git_revision": revision, "source_sha256": sources,
                "environment": {"python": platform.python_version(), "system": platform.system(),
                                "machine": platform.machine(), "packages": versions},
                "configuration": config, "dataset_sha256": plan["dataset_sha256"],
                "plan_sha256": digest(args.plan.read_bytes()), "plan": plan["plan"],
                "items": items, "model_cache": model_info}
    return {"status": "BLOCKED" if issues else "PASS", "issues": issues,
            "submission_static_issues": deployment, "contract": contract,
            "git_dirty": dirty, "planned_calls": len(items) * 2,
            "max_calls_with_retries": len(items) * 2 * (1 + args.retries),
            "booklets": booklets, "encoder_path": encoder}


def public_preflight(prepared):
    return {k: v for k, v in prepared.items() if k not in ("booklets", "encoder_path")}


def connect(args):
    os.environ.update(LLM_NAME=MLX_MODEL, LLM_BASE_URL=endpoint(args.endpoint),
                      LLM_CONTEXT_TOKENS=str(args.context), LLM_TOKEN_PREFLIGHT="required")
    judge = SubmissionJudge(timeout=args.timeout)
    response = judge.session.get(judge.base + "/experiment-metadata", timeout=10)
    response.raise_for_status()
    metadata = response.json()
    if not metadata.get("loaded") or metadata.get("model") != MLX_MODEL or metadata.get("revision") != REVISION:
        raise ValueError("Endpoint has no matching loaded-model provenance; start serve_experiments.py")
    if metadata.get("backend") != "native-mlx" or metadata.get("model_class") != "mlx_lm.models.apertus.Model":
        raise ValueError("Endpoint did not load the expected Apertus implementation")
    if metadata.get("context_tokens") != args.context or metadata.get("chat_template_kwargs") != {"enable_thinking": False}:
        raise ValueError("Endpoint context or chat template differs from the experiment")
    # Only allowlisted metadata is persisted; arbitrary server text/paths are excluded.
    keys = ("model", "revision", "backend", "model_class", "context_tokens", "instance_id", "mlx_lm_version",
            "config_sha256", "shards", "quantisation", "chat_template_kwargs")
    return judge, {k: metadata[k] for k in keys}


def validate_records(contract, records, events):
    expected = {str(i["row_index"]) + ":" + mode: (i, mode)
                for i in contract["items"] for mode in ("full", "retrieved")}
    for collection in (records, events):
        seen = set()
        for record in collection:
            if record.get("schema") != SCHEMA or record.get("key") not in expected:
                raise ValueError("Result schema or matrix key differs from the manifest")
            item, mode = expected[record["key"]]
            if record.get("gold") != item["gold"] or record.get("input") != dict(item["request"], evidence=mode):
                raise ValueError("Result inputs or gold differ from the manifest")
            attempt = record.get("attempt_id")
            if not isinstance(attempt, str) or attempt in seen:
                raise ValueError("Missing or duplicate attempt identity")
            seen.add(attempt)
    for record in records:
        if record.get("status") not in ("completed", "failed", "interrupted"):
            raise ValueError("Invalid result status")
        if record["status"] == "completed" and (record.get("pred") not in CODE_TO_LABEL.values()
                                                or record["result"].get("error")):
            raise ValueError("Completed result has no valid prediction")
        if record["status"] != "completed" and record.get("pred") is not None:
            raise ValueError("Failed result cannot carry a scored prediction")


def summaries(directory, manifest, records, status):
    latest = {}
    for record in records:
        latest[record["key"]] = record
    result = {"schema": SCHEMA, "status": status, "updated_utc": now(),
              "planned": len(manifest["contract"]["items"]) * 2, "attempts": len(records),
              "failed_attempts": sum(r["status"] != "completed" for r in records),
              "completed": sum(r["status"] == "completed" for r in latest.values()),
              "failed": sum(r["status"] != "completed" for r in latest.values()),
              "missing": len(manifest["contract"]["items"]) * 2 - len(latest),
              "verification": {"native_mlx": "measured" if records else "unverified",
                               "docker_inference": "unverified", "cross_platform": "unverified",
                               "identity_basis": "loader instrumentation, not cryptographic attestation"},
              "methods": {}, "prediction_changes": [], "payload_comparison": []}
    for mode in ("full", "retrieved"):
        rows = [r for r in latest.values() if r["method"] == mode]
        if not rows:
            result["methods"][mode] = {"n": 0, "accuracy": None, "macro_f1": None}
            continue
        stats = summarise(rows)
        stats["metric_scope"] = "attempted rows, including failures; missing rows excluded"
        stats["citation_verified"] = sum(r["result"].get("citation_verified", False) for r in rows)
        for field in ("prompt_tokens", "completion_tokens"):
            values = [r["result"].get("usage", {}).get(field) for r in rows]
            measured = [v for v in values if type(v) is int]
            stats[field] = {"measured_total": sum(measured), "measured_rows": len(measured),
                            "missing_rows": len(values) - len(measured)}
        stats["wall_s_all_attempts"] = sum(r["elapsed_s"] for r in records if r["method"] == mode)
        result["methods"][mode] = stats
    paired = {"full": [], "retrieved": []}
    for item in manifest["contract"]["items"]:
        a, b = (latest.get(str(item["row_index"]) + ":" + mode) for mode in ("full", "retrieved"))
        if a and b:
            result["payload_comparison"].append({"row_index": item["row_index"],
                "full_prompt_sha256": a["result"].get("prompt_sha256"),
                "retrieved_prompt_sha256": b["result"].get("prompt_sha256"),
                "full_chars": a.get("evidence_chars"), "retrieved_chars": b.get("evidence_chars")})
            if a["status"] == b["status"] == "completed":
                paired["full"].append(a)
                paired["retrieved"].append(b)
                if a["pred"] != b["pred"]:
                    result["prediction_changes"].append({"row_index": item["row_index"], "gold": item["gold"],
                        "full": a["pred"], "retrieved": b["pred"],
                        "change": "improved" if b["correct"] else "worsened" if a["correct"] else "both_wrong"})
    result["paired_success_only"] = {m: summarise(rows) if rows else {"n": 0} for m, rows in paired.items()}
    write_json(directory / "summary.json", result)
    lines = ["# Paired Apertus v1.5 development results", "", "Status: " + status + ".",
             f"Completed {result['completed']}/{result['planned']}; failed {result['failed']}; missing {result['missing']}.",
             "", "Native MLX only. Docker inference and cross-platform execution remain unverified.",
             "Nine development examples do not establish generalisation; the historical split contains duplicates.",
             "", "| Method | Attempted | Accuracy | Macro-F1 |", "|---|---:|---:|---:|"]
    for mode, metrics in result["methods"].items():
        lines.append(f"| {mode} | {metrics['n']} | {metrics.get('accuracy')} | {metrics.get('macro_f1')} |")
    lines += ["", "Errors count as failed predictions; missing rows are excluded. See summary.json for paired-success metrics,",
              "per-class results, token coverage, earlier failed attempts and prediction changes.",
              "A verified snippet establishes textual provenance, not semantic correctness."]
    (directory / "summary.md").write_text("\n".join(lines) + "\n")
    return result


def make_retriever(snapshot):
    from retriever import Retriever
    retriever = BookletRetriever()
    retriever.encoder = Retriever(model_name=str(snapshot))
    return retriever


def execute(args, prepared):
    directory = output_path(args.out)
    contract = prepared["contract"]
    identity = fingerprint(contract)
    with locked(directory):
        path = directory / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text())
            if not args.resume:
                raise ValueError("Run already exists; use --resume or a new output directory")
            if manifest.get("contract_sha256") != identity:
                raise ValueError("Resume refused: code, dataset, PDFs, environment or configuration changed")
        else:
            if args.resume or (directory / "predictions.jsonl").exists():
                raise ValueError("Cannot resume without the original manifest")
            manifest = {"schema": SCHEMA, "created_utc": now(), "contract_sha256": identity,
                        "contract": contract, "git_dirty": prepared["git_dirty"], "sessions": []}
            write_json(path, manifest)
        (directory / "predictions.jsonl").touch(exist_ok=True)
        records = read_log(directory / "predictions.jsonl")
        events = read_log(directory / "events.jsonl")
        validate_records(contract, records, events)
        completed_attempts = {r["attempt_id"] for r in records}
        for event in events:
            if event["attempt_id"] not in completed_attempts:
                record = dict(event, status="interrupted", pred=None, correct=False, elapsed_s=0,
                              result={"error": "interrupted_outcome_unknown", "label": None})
                append(directory / "predictions.jsonl", record)
                records.append(record)
        summaries(directory, manifest, records, "RUNNING")
        latest = {r["key"]: r for r in records}
        pending = [(n, item, mode) for n, item in enumerate(contract["items"])
                   for mode in (("full", "retrieved") if n % 2 == 0 else ("retrieved", "full"))
                   if str(item["row_index"]) + ":" + mode not in latest or
                   (args.retry_failed and latest[str(item["row_index"]) + ":" + mode]["status"] != "completed")]
        if not pending:
            status = "COMPLETE" if all(r["status"] == "completed" for r in latest.values()) else "COMPLETE_WITH_ERRORS"
            summaries(directory, manifest, records, status)
            return 0 if status == "COMPLETE" else 1
        try:
            judge, metadata = connect(args)
            for key in ("config_sha256", "shards", "mlx_lm_version", "quantisation"):
                if metadata[key] != contract["model_cache"][key]:
                    raise ValueError("Loaded model differs from the preflight cache")
            manifest["sessions"].append(dict(started_utc=now(), endpoint=metadata))
            write_json(path, manifest)
            retriever = make_retriever(prepared["encoder_path"])
        except Exception as exc:
            summaries(directory, manifest, records, "BLOCKED:" + type(exc).__name__)
            print("BLOCKED: model endpoint/provenance or cached encoder unavailable; start the documented server", flush=True)
            return 2
        for position, (_, item, mode) in enumerate(pending, 1):
            key = str(item["row_index"]) + ":" + mode
            for retry in range(args.retries + 1):
                event = {"schema": SCHEMA, "key": key, "attempt_id": uuid.uuid4().hex,
                         "started_utc": now(), "row_index": item["row_index"], "method": mode,
                         "gold": item["gold"], "pair": item["request"]["claim_language"] + "->" + item["request"]["booklet_language"],
                         "input": dict(item["request"], evidence=mode), "server_instance": metadata["instance_id"]}
                append(directory / "events.jsonl", event)
                start = time.perf_counter()
                interrupted = False
                try:
                    request = event["input"]
                    booklet = prepared["booklets"][(request["booklet"], request["booklet_language"])]
                    result = classify(request, judge, retriever, booklet, seed=20261011)
                    evidence = evidence_payload(booklet, result["passages"])
                    event["messages"] = build_messages(request["claim"], evidence)
                    event["evidence_chars"] = len(evidence)
                    event["reference_shingle_coverage"] = coverage(item["reference"], result["passages"])
                except KeyboardInterrupt:
                    result = {"label": None, "error": "interrupted_outcome_unknown"}
                    interrupted = True
                except Exception as exc:
                    result = {"label": None, "error": "pipeline_error:" + type(exc).__name__}
                pred = result.get("label") if not result.get("error") else None
                record = dict(event, result=result, pred=pred, correct=pred == item["gold"],
                              elapsed_s=time.perf_counter() - start, finished_utc=now(),
                              status="interrupted" if interrupted else "completed" if pred in CODE_TO_LABEL.values() else "failed")
                append(directory / "predictions.jsonl", record)
                records.append(record)
                summaries(directory, manifest, records, "INTERRUPTED" if interrupted else "RUNNING")
                print(f"[{position}/{len(pending)}] row {item['row_index']} {event['pair']} {mode}: {record['status']} ({record['elapsed_s']:.1f}s)", flush=True)
                if interrupted:
                    return 130
                error = result.get("error", "")
                transient = error in ("endpoint_or_tokenisation_error:Timeout", "endpoint_or_tokenisation_error:ReadTimeout",
                                      "endpoint_or_tokenisation_error:ConnectTimeout", "endpoint_or_tokenisation_error:ConnectionError")
                if not transient or retry == args.retries:
                    break
                time.sleep(min(2 ** retry, 4))
        latest = {r["key"]: r for r in records}
        status = "COMPLETE" if len(latest) == len(contract["items"]) * 2 and all(
            r["status"] == "completed" for r in latest.values()) else "COMPLETE_WITH_ERRORS"
        result = summaries(directory, manifest, records, status)
        return 0 if result["status"] == "COMPLETE" else 1


def smoke(args):
    """An explicit real make run, with prerequisite failures reported as BLOCKED."""
    directory = output_path(args.out)
    with locked(directory):
        if (directory / "manifest.json").exists():
            raise ValueError("Choose a new smoke output directory")
        manifest = {"schema": SCHEMA, "mode": "submission-smoke", "created_utc": now(),
                    "deployment": args.deployment, "model": MODEL,
                    "git_revision": command(["git", "rev-parse", "HEAD"]).stdout.strip()}
        write_json(directory / "manifest.json", manifest)
        (directory / "predictions.jsonl").touch()
        def finish(status, reason, result=None):
            summary = {"schema": SCHEMA, "status": status, "reason": reason,
                       "docker_inference": status == "PASS", "cross_platform": "unverified",
                       "host": {"system": platform.system(), "machine": platform.machine()}}
            if result is not None:
                append(directory / "predictions.jsonl", {"schema": SCHEMA, "result": result})
            write_json(directory / "summary.json", summary)
            (directory / "summary.md").write_text(f"# Submission smoke\n\n{status}: {reason}\n")
            print(status + ": " + reason)
            return 0 if status == "PASS" else 2 if status == "BLOCKED" else 1
        if not shutil.which("docker") or not shutil.which("make"):
            return finish("BLOCKED", "Docker Compose and GNU Make are required")
        if command(["docker", "info"], timeout=15).returncode:
            return finish("BLOCKED", "Docker daemon is unavailable")
        files = ["-f", "compose.submission.yaml"]
        if args.deployment == "managed":
            files += ["-f", "compose.managed.yaml"]
        compose = ["docker", "compose"] + files
        configured = command(compose + ["config", "--format", "json"])
        if configured.returncode:
            return finish("BLOCKED", "Compose configuration failed")
        configuration = json.loads(configured.stdout)
        app_env = configuration["services"]["app"]["environment"]
        if app_env["LLM_NAME"] != MODEL:
            return finish("BLOCKED", "Submission smoke requires the official v1.5 8B model")
        if args.deployment == "managed":
            info = command(["docker", "info", "--format", "{{json .Runtimes}}"])
            if "nvidia" not in info.stdout:
                return finish("BLOCKED", "Docker has no NVIDIA runtime")
            if not configuration["services"]["apertus"]["environment"].get("HF_TOKEN"):
                return finish("BLOCKED", "Set HF_TOKEN for gated official model access")
        elif not app_env.get("LLM_BASE_URL") or "apertus:8000" in app_env["LLM_BASE_URL"]:
            return finish("BLOCKED", "Set LLM_BASE_URL to a provisioned official v1.5 endpoint")
        else:
            import requests
            base = endpoint(app_env["LLM_BASE_URL"])
            # This host probe is a prerequisite check, never Docker networking evidence.
            probe_base = base.replace("host.docker.internal", "127.0.0.1")
            try:
                headers = {"Authorization": "Bearer " + app_env["LLM_API_KEY"]} if app_env.get("LLM_API_KEY") else {}
                response = requests.get(probe_base + "/v1/models", headers=headers, timeout=10)
                response.raise_for_status()
                if MODEL not in [r["id"] for r in response.json()["data"]]:
                    return finish("BLOCKED", "External endpoint does not list the official v1.5 model")
            except Exception:
                return finish("BLOCKED", "External endpoint unavailable or credentials rejected")
        request_path = args.request.resolve()
        if not request_path.is_file():
            return finish("BLOCKED", "Request file is missing")
        request = json.loads(request_path.read_text())
        validate_request(request)
        if request["booklet"].startswith(("/Users/", "/home/")):
            return finish("BLOCKED", "Use an HTTPS booklet URL or a /app/data/ container path")
        write_json(directory / "request.json", request)
        container_dir = "/app/" + directory.relative_to(PROJECT_ROOT.resolve()).as_posix()
        env = dict(os.environ, REQUEST_FILE=container_dir + "/request.json", RESULT_FILE=container_dir + "/result.json")
        # Compose obtains secrets from the existing environment/.env; never save its rendered config or logs.
        manifest["request_sha256"] = fingerprint(request)
        manifest["configuration"] = {k: app_env[k] for k in
                                     ("LLM_NAME", "LLM_CONTEXT_TOKENS", "LLM_TOKEN_PREFLIGHT")}
        manifest["configuration"]["endpoint"] = endpoint(app_env["LLM_BASE_URL"])
        manifest["submission_files"] = {p: digest((PROJECT_ROOT / p).read_bytes()) for p in
                                         ("Dockerfile", "Makefile", "compose.submission.yaml", "compose.managed.yaml")}
        write_json(directory / "manifest.json", manifest)
        try:
            proc = command(["make", "run", "SUBMISSION_MODE=" + args.deployment], timeout=args.smoke_timeout, env=env)
        except subprocess.TimeoutExpired:
            command(compose + ["stop"], timeout=30, env=env)
            return finish("FAIL", "Deployment timeout; services stopped, caches retained")
        except KeyboardInterrupt:
            command(compose + ["stop"], timeout=30, env=env)
            return finish("FAIL", "Interrupted deployment; services stopped, caches retained")
        result_path = directory / "result.json"
        if not result_path.exists():
            return finish("BLOCKED", "make run produced no result; inspect Docker startup, GPU, access and bind-mount permissions")
        result = json.loads(result_path.read_text())
        if proc.returncode or result.get("error") or result.get("model") != MODEL or result.get("response_model") != MODEL:
            return finish("FAIL", "Application or model verification failed", result)
        if not result.get("citation_verified") or result.get("label_code") not in (0, 1, 2):
            return finish("FAIL", "No valid label with a verified citation", result)
        if any(result.get(k) != request[k] for k in ("claim", "booklet", "claim_language", "booklet_language")):
            return finish("FAIL", "Result does not match the requested booklet and claim", result)
        return finish("PASS", "One real Docker make run completed; no cross-platform or accuracy claim", result)


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("preflight", "run", "submission-smoke"))
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--plan", type=Path, default=PLAN)
    ap.add_argument("--out", type=Path, default=OUTPUT)
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080")
    ap.add_argument("--context", type=int, default=32768)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--deployment", choices=("managed", "external"), default="managed")
    ap.add_argument("--request", type=Path, default=PROJECT_ROOT / "data/request.json")
    ap.add_argument("--smoke-timeout", type=int, default=2400)
    return ap


def main(argv=None):
    ap = parser()
    args = ap.parse_args(argv)
    if not 512 < args.context <= 262144 or not 0 < args.timeout <= 600 or not 0 <= args.retries <= 2 or not 1 <= args.smoke_timeout <= 7200:
        ap.error("Invalid context, timeout or retries (retries must be 0–2)")
    if args.retry_failed and not args.resume:
        ap.error("--retry-failed requires --resume")
    if args.mode != "run" and (args.resume or args.retry_failed):
        ap.error("Resume options apply only to run")
    try:
        args.out = output_path(args.out)
        if args.mode == "submission-smoke":
            return smoke(args)
        url = urlparse(endpoint(args.endpoint))
        if url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Native experiments require a loopback endpoint")
        prepared = prepare(args)
        write_json(args.out / "preflight.json", public_preflight(prepared))
        print(f"Preflight {prepared['status']}: {prepared['planned_calls']} planned calls, up to {prepared['max_calls_with_retries']} with retries")
        for issue in prepared["issues"] + prepared["submission_static_issues"]:
            print("- " + issue)
        if prepared["issues"]:
            return 2
        if args.mode == "preflight":
            print("No endpoint called, model loaded or download attempted. Docker runtime remains unverified.")
            return 0
        return execute(args, prepared)
    except (Exception, KeyboardInterrupt) as exc:
        # Avoid logging exception text: URLs and OS exceptions can contain credentials or home paths.
        message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("BLOCKED: " + message, file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 2


if __name__ == "__main__":
    sys.exit(main())
