"""Offline evidence diagnosis and an opt-in Oracle-evidence experiment.

``analyse`` and ``validate-oracle`` never contact a model endpoint.  The
``run-oracle`` command is deliberately separate and is the only live mode.
It reuses booklet_app.SubmissionJudge and classify, changing only the evidence
text supplied to the recorded NLI prompt.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse
import uuid

from booklet_app import MLX_MODEL, build_messages, classify, digest
from config import PROJECT_ROOT
from eval_nli import DEFAULT_DATA, load_rows, summarise
from experiment_runner import connect, endpoint, fingerprint, locked, now, output_path
from labels import CODE_TO_LABEL, label_to_code, normalise_label


SCHEMA = "hackapertus-evidence-diagnosis-v1"
ORACLE_SCHEMA = "hackapertus-oracle-evidence-v1"
SOURCE = PROJECT_ROOT / "data/experiments/v15-grouped81-80k"
PLAN = PROJECT_ROOT / "docs/evidence/paired_grouped81_plan_20261011.json"
ANALYSIS_OUT = PROJECT_ROOT / "data/experiments/v15-grouped81-evidence-diagnosis-20261012"
ORACLE_OUT = PROJECT_ROOT / "data/experiments/v15-grouped81-oracle-20261012"
SEED = 20261011
LONG_REFERENCE_CHARS = 12000
RECORDED_PARSER_VERSION = "label-parse-v3-strict"

# The archived run predates parser v3.1.  Keep its small, attributed v3
# parsing policy here so an Oracle comparison does not silently change the
# measurement boundary while still using the current inference client.
_V3_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_V3_LABEL_KEY_RE = re.compile(
    r'"label"\s*:\s*"([^"]*)"'
    r'|"label"\s*:\s*(true|false|null|[0-9]+(?:\.[0-9]+)?)(?![0-9.\w])',
    re.IGNORECASE)
_V3_LEADING_LABEL_RE = re.compile(
    r"\s*(entailment|neutral|contradiction)(?![\w/~\\|-])", re.IGNORECASE)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_jsonl(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path):
    records = []
    data = path.read_bytes() if path.exists() else b""
    for number, line in enumerate(data.splitlines(), 1):
        try:
            records.append(json.loads(line))
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"Invalid JSONL at {path.name}:{number}") from exc
    return records


def latest_by_key(records):
    latest = {}
    for record in records:
        key = record.get("key")
        if not isinstance(key, str):
            raise ValueError("Prediction record has no key")
        latest[key] = record
    return latest


def case_status(record):
    if record.get("status") == "completed" and record.get("pred") in CODE_TO_LABEL.values():
        return "correct" if record.get("correct") else "incorrect"
    error = (record.get("result") or {}).get("error")
    if error == "incomplete_completion" or (record.get("result") or {}).get("finish_reason") == "length":
        return "incomplete"
    return "invalid"


def reference_flags(text):
    stripped = text.strip() if isinstance(text, str) else ""
    return {
        "missing": not bool(stripped),
        "chars": len(text) if isinstance(text, str) else 0,
        "unusually_long": len(text) > LONG_REFERENCE_CHARS if isinstance(text, str) else False,
        "possible_truncation": stripped.endswith(("...", "…")),
        "semantic_sufficiency": "not_established_by_automated_checks",
    }


def parse_recorded_v3(raw):
    """Reproduce the parser named in the archived 81-case manifest."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    match = _V3_JSON_RE.search(text)
    if match:
        try:
            obj = json.loads(match.group(0))
            label = normalise_label(obj.get("label"))
            if label:
                obj["label"] = label
                return obj
        except json.JSONDecodeError:
            pass
    match = _V3_LABEL_KEY_RE.search(text)
    raw_label = None
    if match:
        raw_label = match.group(1) if match.group(1) is not None else match.group(2)
    if raw_label is None:
        match = _V3_LEADING_LABEL_RE.match(text)
        if match:
            raw_label = match.group(1)
    label = normalise_label(raw_label) if raw_label is not None else None
    if label:
        return {"label": label, "reasoning": text[:200], "evidence_snippet": ""}
    return {"label": None, "reasoning": "Unparseable response: " + text[:120],
            "evidence_snippet": "", "error": "unparseable_response"}


def apply_recorded_parser(result):
    """Apply v3 only after successful transport/completion validation."""
    output = dict(result)
    output["parser_version"] = RECORDED_PARSER_VERSION
    if not isinstance(output.get("raw_response"), str):
        return output
    if output.get("error") not in (None, "unparseable_response"):
        return output
    parsed = parse_recorded_v3(output["raw_response"])
    for key in ("label", "reasoning", "evidence_snippet"):
        output[key] = parsed.get(key)
    output["label_code"] = label_to_code(output["label"])
    if parsed.get("error"):
        output["error"] = parsed["error"]
    else:
        output.pop("error", None)
    return output


class RecordedParserJudge:
    """Delegate inference to SubmissionJudge, then pin archived v3 parsing."""
    def __init__(self, judge):
        self.judge_client = judge

    def judge(self, claim, evidence, seed=SEED):
        return apply_recorded_parser(self.judge_client.judge(claim, evidence, seed=seed))


def validate_source(data_path, plan_path, source_dir):
    required = [plan_path, data_path] + [source_dir / name for name in
        ("manifest.json", "predictions.jsonl", "summary.json")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError("Missing source artefact: " + ", ".join(missing))
    rows = load_rows(data_path)
    plan = json.loads(plan_path.read_text())
    source_manifest = json.loads((source_dir / "manifest.json").read_text())
    indices = plan.get("plan", {}).get("row_indices")
    if not isinstance(indices, list) or len(indices) != 81 or len(indices) != len(set(indices)):
        raise ValueError("Expected 81 unique frozen plan rows")
    dataset_hash = sha256_file(data_path)
    if plan.get("dataset_sha256") != dataset_hash:
        raise ValueError("Frozen plan dataset hash mismatch")
    contract = source_manifest.get("contract", {})
    if contract.get("dataset_sha256") != dataset_hash or contract.get("plan_sha256") != sha256_file(plan_path):
        raise ValueError("Recorded experiment does not identify the supplied dataset and plan")
    contract_indices = [item.get("row_index") for item in contract.get("items", [])]
    if contract_indices != indices:
        raise ValueError("Recorded experiment matrix differs from the frozen plan")
    records = read_jsonl(source_dir / "predictions.jsonl")
    latest = latest_by_key(records)
    expected = {f"{index}:{mode}" for index in indices for mode in ("full", "retrieved")}
    if set(latest) != expected:
        raise ValueError("Recorded results do not account for exactly all 162 planned calls")
    return rows, plan, source_manifest, records, latest


def select_controls(indices, latest):
    """Select the lowest row ID per label among correct, citation-verified cases."""
    controls = []
    for label in ("entailment", "neutral", "contradiction"):
        candidates = [latest[f"{index}:retrieved"] for index in indices
                      if latest[f"{index}:retrieved"].get("status") == "completed"
                      and latest[f"{index}:retrieved"].get("correct") is True
                      and latest[f"{index}:retrieved"].get("gold") == label
                      and (latest[f"{index}:retrieved"].get("result") or {}).get("citation_verified") is True]
        if candidates:
            controls.append(min(record["row_index"] for record in candidates))
    return controls


def build_case(index, row, full, retrieved, data_path):
    result = retrieved.get("result") or {}
    status = case_status(retrieved)
    reference = row.get("reference_string")
    return {
        "case_id": str(index),
        "row_index": index,
        "claim": row.get("claim"),
        "claim_language": row.get("claim_language"),
        "booklet_language": row.get("reference_language"),
        "vote": row.get("vote"),
        "booklet_url": row.get("booklet_url"),
        "gold": CODE_TO_LABEL[row["entailment_label"]],
        "predicted": retrieved.get("pred"),
        "status": status,
        "correct": status == "correct",
        "error": result.get("error"),
        "finish_reason": result.get("finish_reason"),
        "citation": {
            "verified": result.get("citation_verified") is True,
            "snippet": result.get("evidence_snippet"),
            "records": result.get("citations") or [],
            "meaning": "strict textual provenance only; not semantic evidence correctness",
        },
        "retrieved_evidence": result.get("passages") or [],
        "retrieved_evidence_chars": retrieved.get("evidence_chars"),
        "reference_shingle_coverage": retrieved.get("reference_shingle_coverage"),
        "annotated_reference": {
            "dataset": str(data_path.relative_to(PROJECT_ROOT)),
            "dataset_row_index": index,
            "language": row.get("reference_language"),
            "text": reference,
            "sha256": digest((reference or "").encode()),
            "flags": reference_flags(reference),
        },
        "full_booklet_baseline": {
            "predicted": full.get("pred"),
            "status": case_status(full),
            "correct": full.get("correct") is True,
            "error": (full.get("result") or {}).get("error"),
        },
    }


def source_identities(data_path, plan_path, source_dir):
    paths = [data_path, plan_path] + [source_dir / name for name in
        ("manifest.json", "predictions.jsonl", "summary.json", "summary.md", "events.jsonl", "preflight.json")]
    return {str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in paths if path.is_file()}


def make_oracle_plan(cases, controls, identities, source_manifest):
    selected = [case for case in cases if case["status"] in ("incorrect", "incomplete", "invalid")
                or case["row_index"] in controls]
    items = []
    for case in selected:
        reference = case["annotated_reference"]
        role = "diagnostic_error" if case["status"] != "correct" else "correct_control"
        items.append({
            "row_index": case["row_index"], "role": role,
            "claim": case["claim"], "claim_language": case["claim_language"],
            "reference": reference["text"], "reference_language": reference["language"],
            "reference_sha256": reference["sha256"], "reference_flags": reference["flags"],
            "gold": case["gold"], "retrieved_prediction": case["predicted"],
            "retrieved_status": case["status"], "full_prediction": case["full_booklet_baseline"]["predicted"],
        })
    configuration = source_manifest["contract"]["configuration"]
    return {
        "schema": ORACLE_SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Diagnostic only: replace retrieved passages with the annotated reference; never production retrieval.",
        "source_identities": identities,
        "selection": {
            "rule": "all retrieved-evidence incorrect, incomplete or invalid cases, plus the lowest row ID correct citation-verified control for each gold label",
            "error_cases": sum(item["role"] == "diagnostic_error" for item in items),
            "controls": controls,
            "n": len(items),
        },
        "inference_contract": {
            "model": configuration["model"], "revision": configuration["revision"],
            "context_tokens": configuration["context_tokens"], "max_tokens": configuration["max_tokens"],
            "temperature": configuration["temperature"], "seed": configuration["seed"],
            "parser_version": configuration["parser_version"],
            "system_prompt_sha256": digest(build_messages("CLAIM", "EVIDENCE")[0]["content"].encode()),
            "only_intended_change": "evidence payload: annotated reference replaces retrieved passages",
        },
        "items": items,
    }


def render_errors(cases):
    problems = [case for case in cases if case["status"] != "correct"]
    lines = ["# Retrieved-evidence diagnostic review", "",
             f"All {len(cases)} frozen cases are accounted for. This review contains {len(problems)} incorrect, incomplete or invalid cases.", "",
             "Citation verification means only that the model returned a verbatim snippet from supplied evidence. It does not establish that the evidence is sufficient or semantically supports the label.", ""]
    for case in problems:
        coverage = case["reference_shingle_coverage"]
        cov = "missing" if coverage is None else f"{coverage:.3f}"
        lines += [f"## Row {case['row_index']} — {case['status']}", "",
                  f"- Pair: {case['claim_language']}→{case['booklet_language']}; vote: {case['vote']}",
                  f"- Gold / retrieved / full: {case['gold']} / {case['predicted']} / {case['full_booklet_baseline']['predicted']}",
                  f"- Citation verified: {str(case['citation']['verified']).lower()}; reference-shingle coverage: {cov}",
                  f"- Error: {case['error'] or 'none'}", f"- Claim: {case['claim']}"]
        if coverage is not None and coverage < 0.05:
            lines.append("- Review flag: under 5% annotated-reference shingle coverage; this is a wrong-topic/insufficient-evidence warning, not semantic proof.")
        if case["citation"]["snippet"]:
            snippet = " ".join(case["citation"]["snippet"].split())
            lines.append("- Returned snippet: " + snippet[:500] + ("…" if len(snippet) > 500 else ""))
        lines.append("")
    return "\n".join(lines)


def analyse(args):
    out = output_path(args.out)
    if any(out.iterdir()):
        raise ValueError("Analysis output directory is not empty; choose a new directory")
    rows, plan, source_manifest, records, latest = validate_source(args.data, args.plan, args.source)
    indices = plan["plan"]["row_indices"]
    cases = [build_case(index, rows[index], latest[f"{index}:full"], latest[f"{index}:retrieved"], args.data)
             for index in indices]
    statuses = Counter(case["status"] for case in cases)
    matrix = {"label_correct": {"citation_verified": 0, "citation_not_verified": 0},
              "label_incorrect": {"citation_verified": 0, "citation_not_verified": 0}}
    for case in cases:
        if case["status"] not in ("correct", "incorrect"):
            continue
        row = "label_correct" if case["status"] == "correct" else "label_incorrect"
        col = "citation_verified" if case["citation"]["verified"] else "citation_not_verified"
        matrix[row][col] += 1
    full_records = [latest[f"{index}:full"] for index in indices]
    retrieved_records = [latest[f"{index}:retrieved"] for index in indices]
    controls = select_controls(indices, latest)
    identities = source_identities(args.data, args.plan, args.source)
    oracle_plan = make_oracle_plan(cases, controls, identities, source_manifest)
    summary = {
        "schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source.relative_to(PROJECT_ROOT)), "planned_cases": len(indices),
        "accounted_cases": len(cases), "statuses": dict(statuses), "citation_label_matrix": matrix,
        "metrics": {"full_booklet": summarise(full_records), "retrieved": summarise(retrieved_records),
                    "retrieved_success_only": summarise([r for r in retrieved_records if case_status(r) in ("correct", "incorrect")])},
        "error_taxonomy": {
            "incorrect_with_verified_citation": matrix["label_incorrect"]["citation_verified"],
            "incorrect_without_verified_citation": matrix["label_incorrect"]["citation_not_verified"],
            "incomplete": statuses.get("incomplete", 0), "invalid": statuses.get("invalid", 0),
            "problem_cases_with_reference_coverage_below_0_05": sum(
                case["status"] != "correct" and case["reference_shingle_coverage"] is not None
                and case["reference_shingle_coverage"] < 0.05 for case in cases),
            "problem_cases_where_full_booklet_was_correct": sum(
                case["status"] != "correct" and case["full_booklet_baseline"]["correct"] for case in cases),
        },
        "interpretation_limits": [
            "Strict citation verification proves textual provenance only, not semantic relevance or sufficiency.",
            "Reference-shingle coverage is a lexical warning signal, not a semantic evidence score.",
            "The frozen 81 cases are exploratory and not an independent held-out benchmark.",
            "Oracle outcomes are absent until run-oracle is executed manually.",
        ],
        "oracle_plan": {"file": "oracle_plan.json", **oracle_plan["selection"]},
    }
    with (out / "cases.jsonl").open("x", encoding="utf-8") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False, allow_nan=False) + "\n")
    write_json(out / "summary.json", summary)
    write_json(out / "oracle_plan.json", oracle_plan)
    (out / "errors.md").write_text(render_errors(cases) + "\n", encoding="utf-8")
    outputs = {name: sha256_file(out / name) for name in ("summary.json", "cases.jsonl", "errors.md", "oracle_plan.json")}
    manifest = {"schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
                "inputs": identities, "outputs": outputs,
                "note": "Generated offline; no endpoint or model inference was used."}
    write_json(out / "manifest.json", manifest)
    print(f"Accounted for {len(cases)}/81 cases; incorrect={statuses.get('incorrect', 0)}, incomplete={statuses.get('incomplete', 0)}, invalid={statuses.get('invalid', 0)}")
    print("Wrote " + str(out))
    return 0


def validate_oracle_plan(path, data_path):
    plan = json.loads(path.read_text())
    if plan.get("schema") != ORACLE_SCHEMA or not isinstance(plan.get("items"), list):
        raise ValueError("Invalid Oracle plan schema")
    rows = load_rows(data_path)
    identities = plan.get("source_identities", {})
    if identities.get(str(data_path.relative_to(PROJECT_ROOT))) != sha256_file(data_path):
        raise ValueError("Oracle plan dataset identity mismatch")
    root = PROJECT_ROOT.resolve()
    for relative, expected_hash in identities.items():
        source = (root / relative).resolve()
        if source != root and root not in source.parents:
            raise ValueError("Oracle source identity escapes the project root")
        if not source.is_file() or sha256_file(source) != expected_hash:
            raise ValueError("Oracle source identity mismatch: " + relative)
    contract = plan.get("inference_contract", {})
    expected_contract = {"max_tokens": 512, "temperature": 0, "seed": SEED,
                         "parser_version": RECORDED_PARSER_VERSION,
                         "system_prompt_sha256": digest(build_messages("CLAIM", "EVIDENCE")[0]["content"].encode())}
    if any(contract.get(key) != value for key, value in expected_contract.items()):
        raise ValueError("Oracle prompt, decoding or parser contract differs from the recorded experiment")
    seen = set()
    for item in plan["items"]:
        index = item.get("row_index")
        if type(index) is not int or index in seen or not 0 <= index < len(rows):
            raise ValueError("Oracle plan has duplicate or invalid row")
        seen.add(index)
        row = rows[index]
        expected = {"claim": row["claim"], "claim_language": row["claim_language"],
                    "reference": row["reference_string"], "reference_language": row["reference_language"],
                    "reference_sha256": digest(row["reference_string"].encode()),
                    "gold": CODE_TO_LABEL[row["entailment_label"]]}
        if any(item.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Oracle item {index} differs from the dataset")
        messages = build_messages(item["claim"], item["reference"])
        if messages != build_messages(row["claim"], row["reference_string"]):
            raise ValueError("Oracle messages contain more than the claim and reference evidence")
    selection = plan.get("selection", {})
    if selection.get("n") != len(plan["items"]) or selection.get("error_cases") != sum(
            item.get("role") == "diagnostic_error" for item in plan["items"]):
        raise ValueError("Oracle selection counts are inconsistent")
    return plan


def validate_oracle(args):
    plan = validate_oracle_plan(args.oracle_plan, args.data)
    flags = Counter()
    for item in plan["items"]:
        for key in ("missing", "unusually_long", "possible_truncation"):
            flags[key] += bool(item["reference_flags"][key])
    print(f"Oracle plan PASS: {len(plan['items'])} cases ({plan['selection']['error_cases']} errors, {len(plan['selection']['controls'])} controls)")
    print("Reference flags: " + ", ".join(f"{key}={value}" for key, value in flags.items()))
    print("No endpoint was contacted and no inference occurred.")
    return 0


def oracle_request(item):
    """Return the only fields allowed to influence an Oracle model call."""
    return {"task": "beginner", "claim": item["claim"],
            "claim_language": item["claim_language"], "reference": item["reference"],
            "reference_language": item["reference_language"]}


def validate_oracle_records(plan, records, events):
    items = {str(item["row_index"]): item for item in plan["items"]}
    for collection in (records, events):
        attempts = set()
        for record in collection:
            if record.get("schema") != ORACLE_SCHEMA or record.get("key") not in items:
                raise ValueError("Oracle result schema or case differs from the frozen plan")
            attempt = record.get("attempt_id")
            if not isinstance(attempt, str) or attempt in attempts:
                raise ValueError("Oracle record has a missing or duplicate attempt identity")
            attempts.add(attempt)
    for record in records:
        item = items[record["key"]]
        if (record.get("gold") != item["gold"] or record.get("role") != item["role"]
                or record.get("reference_sha256") != item["reference_sha256"]
                or record.get("messages") != build_messages(item["claim"], item["reference"])):
            raise ValueError("Oracle result inputs or evaluation identity differ from the plan")
        if record.get("status") not in ("completed", "failed", "interrupted"):
            raise ValueError("Invalid Oracle result status")
        if record["status"] == "completed" and (record.get("pred") not in CODE_TO_LABEL.values()
                                                 or (record.get("result") or {}).get("error")):
            raise ValueError("Completed Oracle result has no valid prediction")
        if record["status"] != "completed" and record.get("pred") is not None:
            raise ValueError("Failed Oracle result cannot carry a scored prediction")


def oracle_summary(directory, plan, records, status):
    latest = latest_by_key(records)
    rows = list(latest.values())
    successful = [record for record in rows if record.get("status") == "completed"]
    scored_rows = [dict(record, error=(record.get("result") or {}).get("error")) for record in rows]
    scored_successful = [dict(record, error=None) for record in successful]
    result = {
        "schema": ORACLE_SCHEMA, "status": status, "updated_utc": now(),
        "planned": len(plan["items"]), "attempts": len(records), "completed": len(successful),
        "failed": sum(record.get("status") != "completed" for record in rows),
        "missing": len(plan["items"]) - len(rows),
        "metrics_attempted": summarise(scored_rows) if rows else {"n": 0},
        "metrics_success_only": summarise(scored_successful) if successful else {"n": 0},
        "diagnostic_error_changes": Counter(), "controls": Counter(),
        "warning": "Oracle evidence is diagnostic only; it must never enter production retrieval.",
    }
    item_by_id = {str(item["row_index"]): item for item in plan["items"]}
    for record in rows:
        item = item_by_id[record["key"]]
        bucket = result["diagnostic_error_changes"] if item["role"] == "diagnostic_error" else result["controls"]
        if record["status"] != "completed":
            bucket["failed"] += 1
        elif record["pred"] == item["gold"] and item["retrieved_prediction"] != item["gold"]:
            bucket["improved"] += 1
        elif record["pred"] != item["gold"] and item["retrieved_prediction"] == item["gold"]:
            bucket["worsened"] += 1
        elif record["pred"] == item["retrieved_prediction"]:
            bucket["unchanged"] += 1
        else:
            bucket["changed_other"] += 1
    result["diagnostic_error_changes"] = dict(result["diagnostic_error_changes"])
    result["controls"] = dict(result["controls"])
    write_json(directory / "summary.json", result)
    return result


def run_oracle(args):
    plan = validate_oracle_plan(args.oracle_plan, args.data)
    contract = plan["inference_contract"]
    if args.context != contract["context_tokens"]:
        raise ValueError("Oracle context must match the recorded retrieved experiment")
    if urlparse(endpoint(args.endpoint)).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Oracle experiment requires a loopback endpoint")
    directory = output_path(args.out)
    identity = fingerprint({"plan_sha256": sha256_file(args.oracle_plan), "contract": contract})
    with locked(directory):
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if not args.resume or manifest.get("contract_sha256") != identity:
                raise ValueError("Resume refused: use --resume with the unchanged Oracle plan and contract")
        else:
            if args.resume or (directory / "predictions.jsonl").exists():
                raise ValueError("Cannot resume without the original manifest")
            manifest = {"schema": ORACLE_SCHEMA, "created_utc": now(), "contract_sha256": identity,
                        "oracle_plan_sha256": sha256_file(args.oracle_plan), "inference_contract": contract,
                        "sessions": [], "gold_sent_to_model": False, "evaluation_metadata_sent_to_model": False}
            write_json(manifest_path, manifest)
        predictions = directory / "predictions.jsonl"
        predictions.touch(exist_ok=True)
        records = read_jsonl(predictions)
        events_path = directory / "events.jsonl"
        events_path.touch(exist_ok=True)
        events = read_jsonl(events_path)
        validate_oracle_records(plan, records, events)
        completed_attempts = {record["attempt_id"] for record in records}
        items_by_key = {str(item["row_index"]): item for item in plan["items"]}
        for event in events:
            if event["attempt_id"] not in completed_attempts:
                item = items_by_key[event["key"]]
                record = {**event, "finished_utc": now(), "elapsed_s": 0,
                          "status": "interrupted", "gold": item["gold"], "pred": None,
                          "correct": False, "retrieved_prediction": item["retrieved_prediction"],
                          "reference_sha256": item["reference_sha256"],
                          "messages": build_messages(item["claim"], item["reference"]),
                          "result": {"label": None, "error": "interrupted_outcome_unknown"}}
                append_jsonl(predictions, record)
                records.append(record)
        latest = latest_by_key(records)
        valid_keys = {str(item["row_index"]) for item in plan["items"]}
        if not set(latest).issubset(valid_keys):
            raise ValueError("Oracle results contain a case outside the frozen plan")
        pending = [item for item in plan["items"] if str(item["row_index"]) not in latest or
                   (args.retry_failed and latest[str(item["row_index"])].get("status") != "completed")]
        oracle_summary(directory, plan, records, "RUNNING")
        if not pending:
            status = "COMPLETE" if len(latest) == len(plan["items"]) and all(
                record.get("status") == "completed" for record in latest.values()) else "COMPLETE_WITH_ERRORS"
            oracle_summary(directory, plan, records, status)
            return 0 if status == "COMPLETE" else 1
        try:
            judge, metadata = connect(args)
        except Exception as exc:
            oracle_summary(directory, plan, records, "BLOCKED:" + type(exc).__name__)
            print("BLOCKED: matching local model endpoint unavailable", flush=True)
            return 2
        if metadata.get("model") != contract["model"] or metadata.get("revision") != contract["revision"]:
            raise ValueError("Loaded model differs from the frozen Oracle contract")
        judge = RecordedParserJudge(judge)
        manifest["sessions"].append({"started_utc": now(), "endpoint": metadata})
        write_json(manifest_path, manifest)
        for position, item in enumerate(pending, 1):
            for retry in range(args.retries + 1):
                attempt = uuid.uuid4().hex
                event = {"schema": ORACLE_SCHEMA, "key": str(item["row_index"]), "attempt_id": attempt,
                         "started_utc": now(), "row_index": item["row_index"], "role": item["role"],
                         "server_instance": metadata["instance_id"]}
                append_jsonl(events_path, event)
                start = time.perf_counter()
                request = oracle_request(item)
                try:
                    result = classify(request, judge, seed=SEED)
                except KeyboardInterrupt:
                    result = {"label": None, "error": "interrupted_outcome_unknown"}
                except Exception as exc:
                    result = {"label": None, "error": "pipeline_error:" + type(exc).__name__}
                pred = result.get("label") if not result.get("error") else None
                status = "completed" if pred in CODE_TO_LABEL.values() else "interrupted" if result.get(
                    "error") == "interrupted_outcome_unknown" else "failed"
                record = {**event, "finished_utc": now(), "elapsed_s": time.perf_counter() - start,
                          "status": status, "gold": item["gold"], "pred": pred,
                          "correct": pred == item["gold"], "retrieved_prediction": item["retrieved_prediction"],
                          "reference_sha256": item["reference_sha256"],
                          "messages": build_messages(item["claim"], item["reference"]), "result": result}
                append_jsonl(predictions, record)
                records.append(record)
                oracle_summary(directory, plan, records, "INTERRUPTED" if status == "interrupted" else "RUNNING")
                print(f"[{position}/{len(pending)}] row {item['row_index']}: {status} ({record['elapsed_s']:.1f}s)", flush=True)
                if status == "interrupted":
                    return 130
                transient = result.get("error") in (
                    "endpoint_or_tokenisation_error:Timeout", "endpoint_or_tokenisation_error:ReadTimeout",
                    "endpoint_or_tokenisation_error:ConnectTimeout", "endpoint_or_tokenisation_error:ConnectionError")
                if not transient or retry == args.retries:
                    break
                time.sleep(min(2 ** retry, 4))
        latest = latest_by_key(records)
        status = "COMPLETE" if len(latest) == len(plan["items"]) and all(
            record.get("status") == "completed" for record in latest.values()) else "COMPLETE_WITH_ERRORS"
        oracle_summary(directory, plan, records, status)
        return 0 if status == "COMPLETE" else 1


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    analyse_parser = sub.add_parser("analyse", help="analyse the recorded 81-case experiment offline")
    analyse_parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    analyse_parser.add_argument("--plan", type=Path, default=PLAN)
    analyse_parser.add_argument("--source", type=Path, default=SOURCE)
    analyse_parser.add_argument("--out", type=Path, default=ANALYSIS_OUT)
    for name in ("validate-oracle", "run-oracle"):
        command = sub.add_parser(name)
        command.add_argument("--data", type=Path, default=DEFAULT_DATA)
        command.add_argument("--oracle-plan", type=Path, default=ANALYSIS_OUT / "oracle_plan.json")
        if name == "run-oracle":
            command.add_argument("--out", type=Path, default=ORACLE_OUT)
            command.add_argument("--endpoint", default="http://127.0.0.1:8080")
            command.add_argument("--context", type=int, default=81920)
            command.add_argument("--timeout", type=float, default=180)
            command.add_argument("--retries", type=int, choices=(0, 1, 2), default=1)
            command.add_argument("--resume", action="store_true")
            command.add_argument("--retry-failed", action="store_true")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    if getattr(args, "retry_failed", False) and not args.resume:
        raise SystemExit("--retry-failed requires --resume")
    try:
        if args.mode == "analyse":
            return analyse(args)
        if args.mode == "validate-oracle":
            return validate_oracle(args)
        return run_oracle(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
