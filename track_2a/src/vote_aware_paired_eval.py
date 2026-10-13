"""Frozen paired dense-v1 versus vote-aware-v1 CSCS evaluation."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid

from booklet_app import (CANDIDATE_PIPELINE, CSCS_MODEL, FROZEN_PIPELINE,
                         BookletRetriever, SubmissionJudge, build_messages,
                         candidate_evidence, candidate_json, classify, digest,
                         evidence_payload, load_booklet, source_passages,
                         submission_output)
from config import EMBEDDING_MODEL, PROJECT_ROOT
from eval_nli import DEFAULT_DATA, load_rows, summarise
from experiment_runner import (ENCODER_REVISION, append, endpoint, fingerprint,
                               locked, make_retriever, now, output_path,
                               read_log, write_json)
from fetch_booklets import pdf_path
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION

SCHEMA = "hackapertus-vote-aware-paired-v2"
SOURCE_PLAN = PROJECT_ROOT / "docs/evidence/paired_grouped81_plan_20261011.json"
OUTPUT = PROJECT_ROOT / "data/experiments/vote-aware-paired-v2"
PLAN_NAME = "plan.json"
MANIFEST_NAME = "manifest.json"
ARMS = (FROZEN_PIPELINE, CANDIDATE_PIPELINE)
TOP_K = 5
MAX_TOKENS = 512
SELECTION_SEED = 20261013


class FrozenRetriever:
    def __init__(self, passages):
        self.passages = passages

    def retrieve(self, booklet, query, top_k=TOP_K):
        if top_k != TOP_K:
            raise ValueError("Frozen evaluation requires top_k=5")
        return [dict(row) for row in self.passages]


def git_state():
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                              text=True, capture_output=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=PROJECT_ROOT,
                            text=True, capture_output=True, check=True).stdout.splitlines()
    return revision, status


def source_hashes():
    paths = ["src/booklet_app.py", "src/vote_aware_paired_eval.py",
             "src/retriever.py", "src/nli_judge.py", "src/labels.py"]
    return {name: digest((PROJECT_ROOT / name).read_bytes()) for name in paths}


def selected_indices(rows, source_plan):
    chosen, counts = [], Counter()
    for index in source_plan["plan"]["row_indices"]:
        row = rows[index]
        cell = (row["claim_language"], row["reference_language"], row["entailment_label"])
        if counts[cell] < 2:
            chosen.append(index)
            counts[cell] += 1
    expected = Counter((a, b, label) for a in ("de", "fr", "it")
                       for b in ("de", "fr", "it") for label in CODE_TO_LABEL)
    expected = Counter({key: 2 for key in expected})
    if counts != expected or len(chosen) != 54:
        raise ValueError("Source plan cannot supply the requested balanced 54-case sample")
    return chosen


def cached_booklet(row):
    path = pdf_path(row["booklet_url"])
    if not path.is_file():
        raise FileNotFoundError("Missing cached PDF: " + path.name)
    booklet = load_booklet(str(path), row["reference_language"])
    booklet["source"] = row["booklet_url"]
    return booklet


def make_plan(directory, data=DEFAULT_DATA):
    target = directory / PLAN_NAME
    if target.exists():
        return validate_plan(json.loads(target.read_text()), data)
    rows = load_rows(data)
    source = json.loads(SOURCE_PLAN.read_text())
    if digest(data.read_bytes()) != source["dataset_sha256"]:
        raise ValueError("Dataset differs from the existing grouped source plan")
    indices = selected_indices(rows, source)
    revision, status = git_state()
    booklets, cases = {}, []
    for index in indices:
        row = rows[index]
        key = (row["booklet_url"], row["reference_language"])
        if key not in booklets:
            booklets[key] = cached_booklet(row)
        booklet = booklets[key]
        cases.append({"row_index": index, "case_id": "official-row-" + str(index),
                      "claim_language": row["claim_language"],
                      "booklet_language": row["reference_language"],
                      "gold": CODE_TO_LABEL[row["entailment_label"]],
                      "vote": row["vote"], "booklet_url": row["booklet_url"],
                      "pdf_sha256": booklet["sha256"]})
    plan = {"schema": SCHEMA, "experiment_version": "vote-aware-paired-v2",
            "created_utc": now(), "status": "frozen-before-inference",
            "dataset": str(data.relative_to(PROJECT_ROOT)),
            "dataset_sha256": digest(data.read_bytes()),
            "source_plan": str(SOURCE_PLAN.relative_to(PROJECT_ROOT)),
            "source_plan_sha256": digest(SOURCE_PLAN.read_bytes()),
            "selection_seed": SELECTION_SEED,
            "sampling": "first two rows per language-pair/label cell in the existing content-grouped 81-case plan",
            "limitations": ["paired exploratory development evaluation; historical partitions overlap",
                            "gold labels are used only for balanced sampling and scoring"],
            "arms": {FROZEN_PIPELINE: "original claim-only SwissBERT Top-5, original prompt and citation handling",
                     CANDIDATE_PIPELINE: "vote+claim SwissBERT Top-5, vote/attribution prompt and strict source references"},
            "configuration": {"model": CSCS_MODEL, "endpoint": "https://api.inference.cscs.ch/v1",
                              "temperature": 0, "seed": None, "max_tokens": MAX_TOKENS,
                              "token_preflight": "optional", "top_k": TOP_K,
                              "encoder": EMBEDDING_MODEL, "encoder_revision": ENCODER_REVISION,
                              "parser_version": LABEL_PARSE_VERSION,
                              "call_order": "alternating AB/BA", "planned_calls": 108,
                              "retry_policy": "one retry only for ConnectionError or Timeout; all other failures final"},
            "git_revision": revision, "git_status": status, "source_sha256": source_hashes(),
            "cases": cases}
    validate_plan(plan, data)
    write_json(target, plan)
    return plan


def validate_plan(plan, data=DEFAULT_DATA):
    if plan.get("schema") != SCHEMA or plan.get("status") != "frozen-before-inference":
        raise ValueError("Invalid or unfrozen plan")
    if digest(data.read_bytes()) != plan.get("dataset_sha256"):
        raise ValueError("Dataset hash differs from frozen plan")
    if digest(SOURCE_PLAN.read_bytes()) != plan.get("source_plan_sha256"):
        raise ValueError("Source selection plan hash differs")
    cases = plan.get("cases")
    if not isinstance(cases, list) or len(cases) != 54 or len({c.get("row_index") for c in cases}) != 54:
        raise ValueError("Plan must contain 54 unique cases")
    cells = Counter((c.get("claim_language"), c.get("booklet_language"), c.get("gold")) for c in cases)
    if set(cells.values()) != {2} or len(cells) != 27:
        raise ValueError("Plan is not 9 language pairs x 3 labels x 2 examples")
    if plan.get("configuration", {}).get("planned_calls") != 108:
        raise ValueError("Plan must contain exactly 108 primary calls")
    return plan


def prompt_for(request, selected, arm):
    if arm == CANDIDATE_PIPELINE:
        located = source_passages(request["_booklet"], selected)
        evidence = candidate_evidence(located)
        messages = build_messages(request["claim"], evidence, vote=request["vote"], pipeline_version=arm)
        return located, evidence, messages
    evidence = evidence_payload(request["_booklet"], selected)
    return selected, evidence, build_messages(request["claim"], evidence, pipeline_version=arm)


def prepare(directory, data=DEFAULT_DATA):
    plan = make_plan(directory, data)
    target = directory / MANIFEST_NAME
    if target.exists():
        manifest = json.loads(target.read_text())
        validate_manifest(directory, plan, manifest)
        return manifest
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from huggingface_hub import snapshot_download
    snapshot = Path(snapshot_download(EMBEDDING_MODEL, revision=ENCODER_REVISION, local_files_only=True))
    retriever = make_retriever(snapshot)
    rows = load_rows(data)
    cache, items = {}, []
    for case in plan["cases"]:
        row = rows[case["row_index"]]
        key = (row["booklet_url"], row["reference_language"])
        if key not in cache:
            cache[key] = cached_booklet(row)
        booklet = cache[key]
        if booklet["sha256"] != case["pdf_sha256"]:
            raise ValueError("Cached PDF differs from frozen plan")
        base = {"id": case["case_id"], "task": "advanced", "claim": row["claim"],
                "claim_language": row["claim_language"], "booklet": row["booklet_url"],
                "booklet_language": row["reference_language"], "vote": row["vote"],
                "evidence": "retrieved", "top_k": TOP_K, "_booklet": booklet}
        arms = {}
        for arm in ARMS:
            query = row["claim"] if arm == FROZEN_PIPELINE else "Vote: " + row["vote"] + "\nClaim: " + row["claim"]
            started = time.perf_counter()
            selected = retriever.retrieve(booklet, query, TOP_K)
            retrieval_s = time.perf_counter() - started
            located, evidence, messages = prompt_for(base, selected, arm)
            arms[arm] = {"retrieval_query": query, "retrieval_s_prepared": retrieval_s,
                         "passages": located, "evidence_sha256": digest(evidence.encode()),
                         "prompt_sha256": digest(json.dumps(messages, ensure_ascii=False).encode())}
        request = {k: v for k, v in base.items() if k != "_booklet"}
        items.append({"row_index": case["row_index"], "case_id": case["case_id"],
                      "gold": case["gold"], "request": request,
                      "pdf_sha256": case["pdf_sha256"], "arms": arms})
    manifest = {"schema": SCHEMA, "created_utc": now(),
                "plan_sha256": digest((directory / PLAN_NAME).read_bytes()),
                "configuration": plan["configuration"], "items": items,
                "sessions": []}
    validate_manifest(directory, plan, manifest)
    write_json(target, manifest)
    return manifest


def validate_manifest(directory, plan, manifest):
    if manifest.get("schema") != SCHEMA or len(manifest.get("items", [])) != 54:
        raise ValueError("Manifest schema or item count is invalid")
    if manifest.get("plan_sha256") != digest((directory / PLAN_NAME).read_bytes()):
        raise ValueError("Manifest does not match its frozen plan")
    expected = {(c["row_index"], c["case_id"], c["gold"], c["pdf_sha256"]) for c in plan["cases"]}
    actual = {(i.get("row_index"), i.get("case_id"), i.get("gold"), i.get("pdf_sha256")) for i in manifest["items"]}
    if actual != expected:
        raise ValueError("Manifest cases differ from frozen plan")
    for item in manifest["items"]:
        if set(item.get("arms", {})) != set(ARMS):
            raise ValueError("Manifest does not contain both pipeline arms")
        for arm in ARMS:
            data = item["arms"][arm]
            if len(data.get("passages", [])) != TOP_K or not data.get("prompt_sha256"):
                raise ValueError("Frozen retrieval or prompt is incomplete")
    return manifest


def schedule(items):
    calls = []
    for position, item in enumerate(items):
        order = ARMS if position % 2 == 0 else tuple(reversed(ARMS))
        calls.extend((item, arm) for arm in order)
    return calls


def validate_logs(manifest, records, events):
    expected = {str(item["row_index"]) + ":" + arm for item, arm in schedule(manifest["items"])}
    attempts = set()
    for event in events:
        if event.get("schema") != SCHEMA or event.get("key") not in expected:
            raise ValueError("Event differs from the frozen schedule")
        attempt = event.get("attempt_id")
        if not isinstance(attempt, str) or attempt in attempts:
            raise ValueError("Missing or duplicate event attempt ID")
        attempts.add(attempt)
    record_attempts = set()
    for record in records:
        if record.get("schema") != SCHEMA or record.get("key") not in expected:
            raise ValueError("Prediction differs from the frozen schedule")
        attempt = record.get("attempt_id")
        if attempt not in attempts or attempt in record_attempts:
            raise ValueError("Prediction attempt does not match exactly one event")
        record_attempts.add(attempt)
        if record.get("status") not in ("completed", "failed", "interrupted"):
            raise ValueError("Invalid prediction status")


def transient(result):
    return (result.get("error") in ("endpoint_or_tokenisation_error:ConnectionError",
                                    "endpoint_or_tokenisation_error:Timeout") or
            str(result.get("error", "")).endswith("ReadTimeout"))


def verify_runtime_input(item, arm, result, booklet):
    passages = result.get("passages")
    if not isinstance(passages, list):
        raise ValueError("Runtime result omitted frozen passages")
    evidence = candidate_evidence(passages) if arm == CANDIDATE_PIPELINE else evidence_payload(booklet, passages)
    if digest(evidence.encode()) != item["arms"][arm]["evidence_sha256"]:
        raise ValueError("Runtime evidence differs from frozen evidence")
    if result.get("prompt_sha256") != item["arms"][arm]["prompt_sha256"]:
        raise ValueError("Runtime prompt differs from frozen prompt")


def raw_label(result, arm):
    raw = result.get("raw_response")
    if not isinstance(raw, str):
        return None
    try:
        value = candidate_json(raw)[0] if arm == CANDIDATE_PIPELINE else json.loads(raw)
        label = value.get("label") if isinstance(value, dict) else None
        return label if label in CODE_TO_LABEL.values() else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def record_outcome(item, arm, result):
    try:
        official = submission_output(result)
        valid = True
    except (ValueError, TypeError, KeyError):
        official, valid = None, False
    raw = raw_label(result, arm)
    pred = result.get("label") if valid else None
    return {"pred": pred, "raw_label": raw, "raw_correct": raw == item["gold"],
            "strict_correct": pred == item["gold"], "valid_output": valid,
            "submission_output": official}


def binomial_two_sided(b, c):
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def proportion_ci(successes, n):
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = successes / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0, centre - half), 4), round(min(1, centre + half), 4)]


def arm_metrics(records):
    scored = [{"gold": r["gold"], "pred": r.get("pred"), "correct": r.get("strict_correct", False),
               "elapsed_s": (r.get("result") or {}).get("inference_s", 0),
               "retrieval_s": (r.get("result") or {}).get("retrieval_s"),
               "usage": (r.get("result") or {}).get("usage", {}),
               "error": (r.get("result") or {}).get("error")} for r in records]
    metrics = summarise(scored)
    n = len(records)
    valid = sum(r.get("valid_output", False) for r in records)
    raw = sum(r.get("raw_correct", False) for r in records)
    inputs = [(r.get("result") or {}).get("input_tokens") for r in records]
    outputs = [((r.get("result") or {}).get("usage") or {}).get("completion_tokens") for r in records]
    lat = [(r.get("result") or {}).get("inference_s") for r in records]
    ret = [(r.get("result") or {}).get("retrieval_s") for r in records]
    good = lambda values: [v for v in values if type(v) in (int, float) and math.isfinite(v)]
    metrics.update({"raw_label_accuracy": round(raw / n, 4) if n else None,
                    "strict_valid_accuracy": round(sum(r.get("strict_correct", False) for r in records) / n, 4) if n else None,
                    "valid_output_rate": round(valid / n, 4) if n else None,
                    "valid_output_ci95": proportion_ci(valid, n),
                    "native_json_rate": round(sum(isinstance((r.get("result") or {}).get("raw_response"), str)
                                                   and "syntax_recovery" not in (r.get("result") or {})
                                                   and raw_label(r.get("result") or {}, r["arm"]) is not None for r in records) / n, 4) if n else None,
                    "syntax_recovery_rate": round(sum("syntax_recovery" in (r.get("result") or {}) for r in records) / n, 4) if n else None,
                    "parser_failure_rate": round(sum(str((r.get("result") or {}).get("error", "")).startswith("model_response_parse_error") for r in records) / n, 4) if n else None})
    for name, values in (("input_tokens", inputs), ("output_tokens", outputs),
                         ("inference_s", lat), ("retrieval_s", ret)):
        values = good(values)
        metrics[name] = {"total": round(sum(values), 6) if values else None,
                         "mean": round(statistics.mean(values), 6) if values else None,
                         "median": round(statistics.median(values), 6) if values else None,
                         "measured": len(values), "missing": n - len(values)}
    non_neutral = [r for r in records if r.get("raw_label") in ("entailment", "contradiction")]
    metrics["citation_verification_rate"] = round(sum(bool((r.get("result") or {}).get("citation_verified")) for r in records) / n, 4) if n else None
    metrics["non_neutral_citation_validity"] = round(sum(bool((r.get("result") or {}).get("citation_verified")) for r in non_neutral) / len(non_neutral), 4) if non_neutral else None
    if records and records[0]["arm"] == CANDIDATE_PIPELINE:
        statuses = Counter((r.get("result") or {}).get("vote_status") or "missing" for r in records)
        metrics["vote_status"] = dict(statuses)
        metrics["vote_recognition_rate"] = round(statuses["recognised"] / n, 4)
    metrics["failure_types"] = dict(Counter((r.get("result") or {}).get("error") or "none" for r in records))
    return metrics


def summarise_run(directory, manifest, status=None):
    records = read_log(directory / "predictions.jsonl")
    latest = {r["key"]: r for r in records}
    arms = {arm: [latest[k] for k in latest if latest[k]["arm"] == arm] for arm in ARMS}
    planned = 108
    inferred = "INCOMPLETE" if len(latest) != planned else "COMPLETE_WITH_ERRORS" if any(r["status"] != "completed" for r in latest.values()) else "COMPLETE"
    summary = {"schema": SCHEMA, "status": status or inferred, "updated_utc": now(),
               "planned_calls": planned, "attempts": len(records), "accounted_calls": len(latest),
               "missing_calls": planned - len(latest), "arms": {a: arm_metrics(rows) for a, rows in arms.items()},
               "paired": {"a_only_correct": 0, "b_only_correct": 0, "both_correct": 0, "both_incorrect": 0,
                          "disagreements": []}}
    for item in manifest["items"]:
        a = latest.get(str(item["row_index"]) + ":" + FROZEN_PIPELINE)
        b = latest.get(str(item["row_index"]) + ":" + CANDIDATE_PIPELINE)
        if not a or not b:
            continue
        key = "both_correct" if a["strict_correct"] and b["strict_correct"] else "a_only_correct" if a["strict_correct"] else "b_only_correct" if b["strict_correct"] else "both_incorrect"
        summary["paired"][key] += 1
        if a.get("pred") != b.get("pred") or a.get("valid_output") != b.get("valid_output"):
            summary["paired"]["disagreements"].append({"row_index": item["row_index"], "case_id": item["case_id"],
                "language_pair": item["request"]["claim_language"] + "->" + item["request"]["booklet_language"],
                "gold": item["gold"], "dense": a.get("pred"), "vote_aware": b.get("pred"),
                "dense_valid": a.get("valid_output"), "vote_aware_valid": b.get("valid_output"),
                "dense_passages": [p["id"] for p in (a.get("result") or {}).get("passages", [])],
                "vote_aware_passages": [p["id"] for p in (b.get("result") or {}).get("passages", [])],
                "dense_input_tokens": (a.get("result") or {}).get("input_tokens"),
                "vote_aware_input_tokens": (b.get("result") or {}).get("input_tokens"),
                "dense_inference_s": (a.get("result") or {}).get("inference_s"),
                "vote_aware_inference_s": (b.get("result") or {}).get("inference_s")})
    p = summary["paired"]
    p["accuracy_difference"] = round((p["b_only_correct"] - p["a_only_correct"]) / 54, 4)
    p["mcnemar_exact_p"] = round(binomial_two_sided(p["a_only_correct"], p["b_only_correct"]), 6)
    write_json(directory / "summary.json", summary)
    lines = ["# Vote-aware versus dense paired evaluation", "", "Status: " + summary["status"] + ".",
             f"Accounted for {summary['accounted_calls']}/{planned} primary calls; failures remain in denominators.", "",
             "This is a paired exploratory development evaluation, not an independent held-out test.", "",
             "| Arm | N | Accuracy | Macro-F1 | Valid output | Input tokens | Mean latency (s) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        m = summary["arms"][arm]
        lines.append(f"| {arm} | {m['n']} | {m['accuracy']} | {m['macro_f1']} | {m['valid_output_rate']} | {m['input_tokens']['total']} | {m['inference_s']['mean']} |")
    lines += ["", f"Paired strict-accuracy difference (vote-aware minus dense): {p['accuracy_difference']}.",
              f"Exact McNemar p-value: {p['mcnemar_exact_p']}.",
              f"Disagreements or validity changes: {len(p['disagreements'])}.", "",
              "Citation verification establishes mechanical source provenance, not semantic support."]
    if summary["status"] != "COMPLETE":
        lines += ["", "No comparative conclusion is drawn until every planned primary call has an outcome."]
    (directory / "analysis.md").write_text("\n".join(lines) + "\n")
    return summary


def run(directory, endpoint_url, timeout, resume=False):
    plan = validate_plan(json.loads((directory / PLAN_NAME).read_text()))
    manifest = validate_manifest(directory, plan, json.loads((directory / MANIFEST_NAME).read_text()))
    with locked(directory):
        predictions = directory / "predictions.jsonl"
        events = directory / "events.jsonl"
        predictions.touch(exist_ok=True)
        events.touch(exist_ok=True)
        existing = read_log(predictions)
        prior_events = read_log(events)
        validate_logs(manifest, existing, prior_events)
        completed_attempts = {r["attempt_id"] for r in existing}
        for event in prior_events:
            if event["attempt_id"] not in completed_attempts:
                record = dict(event, status="interrupted", pred=None, raw_label=None,
                              raw_correct=False, strict_correct=False, valid_output=False,
                              submission_output=None, elapsed_s=0, finished_utc=now(),
                              result={"label": None, "error": "interrupted_outcome_unknown"})
                append(predictions, record)
                existing.append(record)
        if existing and not resume:
            raise ValueError("Run exists; use --resume")
        latest = {r["key"]: r for r in existing}
        pending = [(item, arm) for item, arm in schedule(manifest["items"])
                   if str(item["row_index"]) + ":" + arm not in latest]
        if not pending:
            return summarise_run(directory, manifest)["status"] == "COMPLETE"
        os.environ.update(LLM_NAME=CSCS_MODEL, LLM_BASE_URL=endpoint(endpoint_url),
                          LLM_CONTEXT_TOKENS="32768", LLM_TOKEN_PREFLIGHT="optional")
        if not os.environ.get("CSCS_INFERENCE_API_KEY"):
            raise ValueError("CSCS_INFERENCE_API_KEY is not available in the environment")
        os.environ["LLM_API_KEY"] = os.environ["CSCS_INFERENCE_API_KEY"]
        judge = SubmissionJudge(timeout=timeout)
        cache = {}
        for item, arm in pending:
            key = str(item["row_index"]) + ":" + arm
            request = dict(item["request"], pipeline_version=arm)
            booklet_key = (request["booklet"], request["booklet_language"])
            if booklet_key not in cache:
                cache[booklet_key] = cached_booklet({"booklet_url": request["booklet"], "reference_language": request["booklet_language"]})
            for attempt_number in (1, 2):
                event = {"schema": SCHEMA, "key": key, "attempt_id": uuid.uuid4().hex,
                         "attempt_number": attempt_number, "started_utc": now(),
                         "row_index": item["row_index"], "case_id": item["case_id"],
                         "arm": arm, "gold": item["gold"], "configured_model": CSCS_MODEL}
                append(events, event)
                started = time.perf_counter()
                try:
                    result = classify(request, judge, FrozenRetriever(item["arms"][arm]["passages"]), cache[booklet_key])
                    verify_runtime_input(item, arm, result, cache[booklet_key])
                    outcome = record_outcome(item, arm, result)
                    status = "completed" if outcome["valid_output"] else "failed"
                except KeyboardInterrupt:
                    result = {"label": None, "error": "interrupted_outcome_unknown"}
                    outcome, status = record_outcome(item, arm, result), "interrupted"
                except Exception as exc:
                    result = {"label": None, "error": "pipeline_error:" + type(exc).__name__}
                    outcome, status = record_outcome(item, arm, result), "failed"
                record = dict(event, result=result, status=status, elapsed_s=time.perf_counter() - started,
                              finished_utc=now(), **outcome)
                append(predictions, record)
                summarise_run(directory, manifest, "RUNNING")
                print(key + " attempt " + str(attempt_number) + ": " + status, flush=True)
                if status == "interrupted":
                    return False
                if not transient(result) or attempt_number == 2:
                    break
        return summarise_run(directory, manifest)["status"] == "COMPLETE"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "prepare", "validate", "run", "summarise"))
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--endpoint", default="https://api.inference.cscs.ch/v1")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        directory = output_path(args.out)
        if args.mode == "plan":
            make_plan(directory, args.data)
            print("Frozen 54 cases and 108 alternating primary calls; no inference performed.")
            return 0
        if args.mode == "prepare":
            prepare(directory, args.data)
            print("Prepared both actual pipeline routes and frozen prompts; no inference performed.")
            return 0
        plan = validate_plan(json.loads((directory / PLAN_NAME).read_text()), args.data)
        manifest = validate_manifest(directory, plan, json.loads((directory / MANIFEST_NAME).read_text()))
        if args.mode == "validate":
            if os.environ.get("CSCS_INFERENCE_API_KEY"):
                print("PASS: frozen plan, PDFs, routes and credential presence; endpoint not called.")
                return 0
            print("BLOCKED: CSCS_INFERENCE_API_KEY is not available; frozen offline preflight passed.", file=sys.stderr)
            return 2
        if args.mode == "summarise":
            summarise_run(directory, manifest)
            return 0
        return 0 if run(directory, args.endpoint, args.timeout, args.resume) else 1
    except Exception as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
