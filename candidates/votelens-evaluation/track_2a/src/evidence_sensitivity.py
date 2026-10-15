"""Standalone evidence sufficiency and order-sensitivity diagnostic.

``freeze``, ``validate`` and ``dry-run`` are offline.  ``run`` is the only mode
that can contact an endpoint, and additionally requires ``--live`` plus fully
approved human annotations.  Production retrieval and submission entry points
are not imported or modified beyond reusing their prompt/client contracts.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time
from urllib.parse import urlparse
import uuid

from booklet_app import (MLX_MODEL, build_messages, digest, evidence_payload,
                         load_booklet, normalise_citation)
from config import PROJECT_ROOT
from eval_nli import DEFAULT_DATA, load_rows, summarise
from experiment_runner import (append, connect, endpoint, fingerprint, locked,
                               now, output_path, read_log, write_json)
from fetch_booklets import pdf_path
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION
from serve_experiments import REVISION


SCHEMA = "hackapertus-evidence-sensitivity-v1"
ANNOTATION_SCHEMA = "hackapertus-evidence-sensitivity-annotations-v1"
ANNOTATIONS = PROJECT_ROOT / "docs/evidence/evidence_sensitivity_annotations_20261012.json"
PLAN = PROJECT_ROOT / "docs/evidence/evidence_sensitivity_plan_20261012.json"
SOURCE = PROJECT_ROOT / "data/experiments/retrieval-ablation-v1"
OUTPUT = PROJECT_ROOT / "data/experiments/evidence-sensitivity-v1"
CONDITIONS = ("A_original", "B_minimal", "C_minimal_plus_distractors", "D_reordered")
DISCORDANT = (29, 119, 297, 432, 442, 455, 1026, 1178, 1344, 1401, 1475)
CONTROLS = (1, 550, 1035, 189, 195, 1058)
SELECTED = DISCORDANT + CONTROLS
SEED = 20261011


def sha256_file(path):
    return digest(path.read_bytes())


def read_jsonl(path):
    records = []
    for number, line in enumerate(path.read_bytes().splitlines(), 1):
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
            raise ValueError("Source prediction has no key")
        latest[key] = record
    return latest


def annotation_spec(annotation):
    """Immutable part of the review file; review decisions may change."""
    cases = []
    for case in annotation.get("cases", []):
        cases.append({key: value for key, value in case.items()
                      if key not in ("review_decision", "reviewer_note")})
    return {"schema": annotation.get("schema"),
            "selection_policy": annotation.get("selection_policy"), "cases": cases}


def annotation_spec_sha256(annotation):
    return fingerprint(annotation_spec(annotation))


def approval_status(annotation):
    decisions = Counter(case.get("review_decision") for case in annotation.get("cases", []))
    approved = (annotation.get("overall_status") == "approved"
                and decisions == Counter({"approved": len(annotation.get("cases", []))})
                and isinstance(annotation.get("reviewer"), str) and annotation["reviewer"].strip()
                and isinstance(annotation.get("reviewed_utc"), str) and annotation["reviewed_utc"].strip())
    return {"approved": bool(approved), "overall_status": annotation.get("overall_status"),
            "decisions": dict(decisions), "reviewer": annotation.get("reviewer"),
            "reviewed_utc": annotation.get("reviewed_utc")}


def source_paths():
    return [DEFAULT_DATA, SOURCE / "manifest.json", SOURCE / "predictions.jsonl",
            SOURCE / "summary.json", PROJECT_ROOT / "src/evidence_sensitivity.py"]


def source_identities():
    return {str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in source_paths()}


def load_sources(annotation_path=ANNOTATIONS):
    required = source_paths()[:-1] + [annotation_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError("Missing source artefact: " + ", ".join(missing))
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    if annotation.get("schema") != ANNOTATION_SCHEMA:
        raise ValueError("Unexpected annotation schema")
    case_indices = [case.get("row_index") for case in annotation.get("cases", [])]
    if case_indices != list(SELECTED) or len(case_indices) != len(set(case_indices)):
        raise ValueError("Annotations must contain the frozen 11 discordant and six control rows in order")
    rows = load_rows(DEFAULT_DATA)
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    latest = latest_by_key(read_jsonl(SOURCE / "predictions.jsonl"))
    configuration = manifest.get("contract", {}).get("configuration", {})
    expected = {"model": MLX_MODEL, "model_revision": REVISION, "temperature": 0,
                "seed": SEED, "max_tokens": 512, "context_tokens": 81920,
                "parser_version": LABEL_PARSE_VERSION}
    for key, value in expected.items():
        if configuration.get(key) != value:
            raise ValueError("Source model/prompt configuration changed: " + key)
    for index in SELECTED:
        for arm in ("A_dense_baseline", "C_hybrid_proposition"):
            record = latest.get(f"{index}:{arm}")
            if not record or record.get("status") != "completed":
                raise ValueError(f"Missing completed source result for row {index} {arm}")
    return annotation, rows, manifest, latest


def find_span(page_text, start, end):
    begin = page_text.find(start)
    if begin < 0:
        raise ValueError("Source-span start anchor not found")
    finish_at = page_text.find(end, begin)
    if finish_at < 0:
        raise ValueError("Source-span end anchor not found")
    finish = finish_at + len(end)
    if page_text.find(start, begin + 1) >= 0:
        raise ValueError("Source-span start anchor is ambiguous")
    return begin, finish, page_text[begin:finish]


def verify_passage(booklet, passage):
    pages = {page["page"]: page["text"] for page in booklet["pages"]}
    if (passage.get("source") != booklet["source"]
            or passage.get("pdf_sha256") != booklet["sha256"]
            or passage.get("page") not in pages
            or passage.get("text") not in pages[passage["page"]]):
        raise ValueError("Evidence passage is not an exact substring of the identified PDF page")


def passage_multiset(passages):
    return sorted((p["source"], p["pdf_sha256"], p["page"], p["text"]) for p in passages)


def condition_payload(booklet, passages):
    return evidence_payload(booklet, passages)


def build_plan(annotation_path=ANNOTATIONS):
    annotation, rows, source_manifest, latest = load_sources(annotation_path)
    booklets = {}
    items = []
    for case in annotation["cases"]:
        index = case["row_index"]
        row = rows[index]
        key = (row["booklet_url"], row["reference_language"])
        if key not in booklets:
            booklet = load_booklet(str(pdf_path(key[0])), key[1])
            booklet["source"] = key[0]
            booklets[key] = booklet
        booklet = booklets[key]
        pages = {page["page"]: page["text"] for page in booklet["pages"]}
        minimal = []
        for number, spec in enumerate(case["source_spans"], 1):
            if spec["page"] not in pages:
                raise ValueError(f"Row {index} source page is absent")
            start, end, quote = find_span(pages[spec["page"]], spec["start"], spec["end"])
            minimal.append({"id": f"row{index}-minimal-{number}", "page": spec["page"],
                            "text": quote, "lang": row["reference_language"],
                            "source": row["booklet_url"], "pdf_sha256": booklet["sha256"],
                            "page_char_start": start, "page_char_end": end,
                            "annotation_status": "pending_review"})
        source_a = latest[f"{index}:A_dense_baseline"]
        source_c = latest[f"{index}:C_hybrid_proposition"]
        original = source_a["result"]["passages"]
        pool = {p["id"]: p for record in (source_c, source_a)
                for p in record["result"]["passages"]}
        distractors = []
        for passage_id in case["distractor_ids"]:
            if passage_id not in pool:
                raise ValueError(f"Row {index} distractor {passage_id} is absent from source A/C")
            distractor = dict(pool[passage_id], annotation_status="pending_review",
                              proposed_role="potential_distractor")
            distractors.append(distractor)
        for passage in original + minimal + distractors:
            verify_passage(booklet, passage)
        condition_passages = {
            CONDITIONS[0]: original,
            CONDITIONS[1]: minimal,
            CONDITIONS[2]: minimal + distractors,
            CONDITIONS[3]: list(reversed(minimal + distractors)),
        }
        if passage_multiset(condition_passages[CONDITIONS[2]]) != passage_multiset(condition_passages[CONDITIONS[3]]):
            raise ValueError("C and D passage multisets differ")
        if condition_passages[CONDITIONS[2]] == condition_passages[CONDITIONS[3]]:
            raise ValueError("C and D order did not change")
        rendered = {name: condition_payload(booklet, evidence)
                    for name, evidence in condition_passages.items()}
        if build_messages(row["claim"], rendered[CONDITIONS[0]]) != source_a.get("messages"):
            raise ValueError(f"Row {index} condition A differs from the recorded SwissBERT prompt")
        c_blocks = sorted(fingerprint(p) for p in condition_passages[CONDITIONS[2]])
        d_blocks = sorted(fingerprint(p) for p in condition_passages[CONDITIONS[3]])
        items.append({
            "row_index": index, "cohort": case["cohort"],
            "claim": row["claim"], "claim_language": row["claim_language"],
            "booklet_language": row["reference_language"], "pair": row["claim_language"] + "->" + row["reference_language"],
            "vote": row["vote"], "booklet_url": row["booklet_url"],
            "pdf_sha256": booklet["sha256"], "gold": CODE_TO_LABEL[row["entailment_label"]],
            "source_A_prediction": source_a["pred"], "source_C_prediction": source_c["pred"],
            "annotation": {key: case[key] for key in ("speaker_attribution", "proposal_identity", "phenomena", "sufficiency_uncertainty")},
            "conditions": {name: {"passages": evidence, "evidence_sha256": digest(rendered[name].encode()),
                                   "evidence_chars": len(rendered[name]),
                                   "message_sha256": digest(json.dumps(build_messages(row["claim"], rendered[name]), ensure_ascii=False).encode())}
                           for name, evidence in condition_passages.items()},
            "C_D_identity": {"same_passage_multiset": c_blocks == d_blocks,
                             "same_passage_count": len(condition_passages[CONDITIONS[2]]) == len(condition_passages[CONDITIONS[3]]),
                             "same_sum_of_passage_chars": sum(len(p["text"]) for p in condition_passages[CONDITIONS[2]]) == sum(len(p["text"]) for p in condition_passages[CONDITIONS[3]]),
                             "only_order_differs": True},
        })
    configuration = source_manifest["contract"]["configuration"]
    return {
        "schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Exploratory diagnostic sample; not an independent benchmark.",
        "selection": {"discordant": list(DISCORDANT), "controls": list(CONTROLS),
                      "n": len(items), "policy": annotation["selection_policy"]},
        "annotation_binding": {"path": str(annotation_path.relative_to(PROJECT_ROOT)),
                               "evidence_spec_sha256": annotation_spec_sha256(annotation),
                               "approval_required_for_live": True},
        "source_identities": source_identities(),
        "source_provenance": {"experiment": str(SOURCE.relative_to(PROJECT_ROOT)),
                              "dataset": str(DEFAULT_DATA.relative_to(PROJECT_ROOT)),
                              "dataset_sha256": sha256_file(DEFAULT_DATA)},
        "inference_contract": {"model": configuration["model"], "revision": configuration["model_revision"],
                               "temperature": configuration["temperature"], "seed": configuration["seed"],
                               "max_tokens": configuration["max_tokens"], "context_tokens": configuration["context_tokens"],
                               "parser_version": configuration["parser_version"],
                               "system_prompt_sha256": configuration["system_prompt_sha256"],
                               "only_intended_variable": "evidence payload"},
        "condition_definitions": {
            CONDITIONS[0]: "Recorded unchanged dense SwissBERT Top-5 evidence.",
            CONDITIONS[1]: "Proposed exact source excerpts only; pending human sufficiency review.",
            CONDITIONS[2]: "Exactly B plus two proposed source-verifiable distractor passages.",
            CONDITIONS[3]: "Exact reverse ordering of C; identical passage multiset and per-passage text."},
        "items": items,
    }


def validate_plan(plan_path=PLAN, annotation_path=ANNOTATIONS, require_approval=False):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    if plan.get("schema") != SCHEMA or len(plan.get("items", [])) != len(SELECTED):
        raise ValueError("Invalid frozen plan schema or case count")
    if plan.get("annotation_binding", {}).get("evidence_spec_sha256") != annotation_spec_sha256(annotation):
        raise ValueError("Annotation evidence specification changed after plan freeze")
    for relative, expected in plan.get("source_identities", {}).items():
        path = (PROJECT_ROOT / relative).resolve()
        if PROJECT_ROOT.resolve() not in path.parents or not path.is_file() or sha256_file(path) != expected:
            raise ValueError("Frozen source identity mismatch: " + relative)
    expected_contract = {"model": MLX_MODEL, "revision": REVISION, "temperature": 0,
                         "seed": SEED, "max_tokens": 512, "context_tokens": 81920,
                         "parser_version": LABEL_PARSE_VERSION}
    for key, value in expected_contract.items():
        if plan["inference_contract"].get(key) != value:
            raise ValueError("Frozen inference contract mismatch: " + key)
    _, rows, _, _ = load_sources(annotation_path)
    for item in plan["items"]:
        row = rows[item["row_index"]]
        booklet = load_booklet(str(pdf_path(row["booklet_url"])), row["reference_language"])
        booklet["source"] = row["booklet_url"]
        if booklet["sha256"] != item["pdf_sha256"]:
            raise ValueError("Booklet hash mismatch")
        for condition in CONDITIONS:
            detail = item["conditions"][condition]
            for passage in detail["passages"]:
                verify_passage(booklet, passage)
            payload = condition_payload(booklet, detail["passages"])
            if digest(payload.encode()) != detail["evidence_sha256"]:
                raise ValueError("Evidence payload changed")
        c = item["conditions"][CONDITIONS[2]]["passages"]
        d = item["conditions"][CONDITIONS[3]]["passages"]
        if passage_multiset(c) != passage_multiset(d) or c == d:
            raise ValueError("C and D must differ only in passage order")
    approval = approval_status(annotation)
    if require_approval and not approval["approved"]:
        raise ValueError("Human annotations remain pending_review; live execution is locked")
    return plan, annotation, approval


def citation_check(result, passages):
    snippet = result.get("evidence_snippet")
    if not isinstance(snippet, str) or not snippet.strip():
        return False, []
    matches = [p for p in passages if normalise_citation(snippet) in normalise_citation(p["text"])]
    return bool(matches), matches


def records_summary(plan, records, status):
    latest = latest_by_key(records)
    summary = {"schema": SCHEMA, "status": status, "updated_utc": now(),
               "planned": len(plan["items"]) * len(CONDITIONS), "attempts": len(records),
               "completed": sum(r.get("status") == "completed" for r in latest.values()),
               "failed": sum(r.get("status") != "completed" for r in latest.values()),
               "missing": len(plan["items"]) * len(CONDITIONS) - len(latest),
               "conditions": {}, "paired_changes": {}, "by_gold": {}, "by_language_pair": {},
               "warning": "Selected exploratory diagnostic sample; do not infer generalisation or model understanding."}
    for condition in CONDITIONS:
        rows = [r for r in latest.values() if r["condition"] == condition]
        scored = [dict(r, error=(r.get("result") or {}).get("error")) for r in rows]
        stats = summarise(scored) if scored else {"n": 0, "accuracy": None, "macro_f1": None}
        usage = defaultdict(list)
        for record in rows:
            result = record.get("result") or {}
            for name in ("prompt_tokens", "completion_tokens"):
                value = (result.get("usage") or {}).get(name)
                if type(value) is int:
                    usage[name].append(value)
            if isinstance(result.get("elapsed_s"), (int, float)):
                usage["latency_s"].append(result["elapsed_s"])
        stats.update(citation_verified=sum((r.get("result") or {}).get("citation_verified") is True for r in rows),
                     token_latency={name: {"total": sum(values), "mean": statistics.mean(values), "n": len(values)}
                                    for name, values in usage.items()})
        summary["conditions"][condition] = stats
        for field, target in (("gold", "by_gold"), ("pair", "by_language_pair")):
            grouped = {}
            for value in sorted({r[field] for r in rows}):
                subset = [dict(r, error=(r.get("result") or {}).get("error")) for r in rows if r[field] == value]
                grouped[value] = summarise(subset)
            summary[target][condition] = grouped
    for left, right, name in ((CONDITIONS[0], CONDITIONS[1], "minimal_vs_original"),
                              (CONDITIONS[1], CONDITIONS[2], "distractor_effect"),
                              (CONDITIONS[2], CONDITIONS[3], "order_sensitivity")):
        changes = Counter()
        details = []
        for item in plan["items"]:
            a, b = latest.get(f"{item['row_index']}:{left}"), latest.get(f"{item['row_index']}:{right}")
            if not a or not b or a.get("status") != "completed" or b.get("status") != "completed":
                changes["unavailable"] += 1
                continue
            if a["pred"] == b["pred"]:
                changes["same_prediction"] += 1
            elif b["correct"] and not a["correct"]:
                changes["right_improved"] += 1
            elif a["correct"] and not b["correct"]:
                changes["right_worsened"] += 1
            else:
                changes["changed_other"] += 1
            if a["pred"] != b["pred"]:
                details.append({"row_index": item["row_index"], "gold": item["gold"],
                                "left": a["pred"], "right": b["pred"]})
        summary["paired_changes"][name] = {"counts": dict(changes), "changes": details}
    return summary


def write_outputs(directory, plan, records, status):
    summary = records_summary(plan, records, status)
    write_json(directory / "summary.json", summary)
    lines = ["# Evidence sensitivity diagnostic", "", f"Status: {status}",
             f"Completed: {summary['completed']}/{summary['planned']}", "",
             "This is a selected exploratory sample, not an independent benchmark.", ""]
    for condition in CONDITIONS:
        stats = summary["conditions"][condition]
        lines.append(f"- {condition}: accuracy={stats.get('accuracy')}, macro-F1={stats.get('macro_f1')}")
    (directory / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def dry_run(args):
    plan, _, approval = validate_plan(args.plan, args.annotations)
    directory = output_path(args.out)
    if any(directory.iterdir()):
        raise ValueError("Dry-run output directory is not empty")
    manifest = {"schema": SCHEMA, "status": "DRY_RUN", "created_utc": now(),
                "plan_sha256": sha256_file(args.plan), "approval": approval,
                "planned_calls": len(plan["items"]) * len(CONDITIONS), "inference_calls": 0,
                "note": "Offline validation only; no endpoint, model or encoder was contacted."}
    write_json(directory / "manifest.json", manifest)
    (directory / "predictions.jsonl").touch()
    write_outputs(directory, plan, [], "DRY_RUN")
    print(f"DRY_RUN PASS: {manifest['planned_calls']} planned calls; inference calls = 0")
    return 0


def run_live(args):
    if not args.live:
        raise ValueError("Live execution requires the explicit --live flag")
    plan, annotation, approval = validate_plan(args.plan, args.annotations, require_approval=True)
    if endpoint(args.endpoint) not in ("http://127.0.0.1:8080", "http://localhost:8080"):
        raise ValueError("Diagnostic live execution requires the pinned loopback endpoint")
    directory = output_path(args.out)
    identity = fingerprint({"plan_sha256": sha256_file(args.plan),
                            "annotation_spec_sha256": annotation_spec_sha256(annotation),
                            "review": approval, "retries": args.retries})
    with locked(directory):
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if not args.resume or manifest.get("contract_sha256") != identity:
                raise ValueError("Resume refused: use --resume with unchanged plan, approval and retries")
        else:
            if args.resume:
                raise ValueError("Cannot resume without the original manifest")
            manifest = {"schema": SCHEMA, "created_utc": now(), "contract_sha256": identity,
                        "plan_sha256": sha256_file(args.plan), "approval": approval,
                        "inference_contract": plan["inference_contract"], "sessions": []}
            write_json(manifest_path, manifest)
        predictions_path = directory / "predictions.jsonl"
        predictions_path.touch(exist_ok=True)
        events_path = directory / "events.jsonl"
        events_path.touch(exist_ok=True)
        records = read_log(predictions_path)
        latest = latest_by_key(records)
        pending = [(item, condition) for item in plan["items"] for condition in CONDITIONS
                   if f"{item['row_index']}:{condition}" not in latest
                   or (args.retry_failed and latest[f"{item['row_index']}:{condition}"]["status"] != "completed")]
        if not pending:
            status = "COMPLETE" if all(r["status"] == "completed" for r in latest.values()) else "COMPLETE_WITH_ERRORS"
            write_outputs(directory, plan, records, status)
            return 0 if status == "COMPLETE" else 1
        judge, metadata = connect(args)
        if metadata["model"] != plan["inference_contract"]["model"] or metadata["revision"] != plan["inference_contract"]["revision"]:
            raise ValueError("Loaded model differs from frozen plan")
        manifest["sessions"].append({"started_utc": now(), "endpoint": metadata})
        write_json(manifest_path, manifest)
        for position, (item, condition) in enumerate(pending, 1):
            key = f"{item['row_index']}:{condition}"
            passages = item["conditions"][condition]["passages"]
            evidence = "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in passages)
            for retry in range(args.retries + 1):
                event = {"schema": SCHEMA, "key": key, "attempt_id": uuid.uuid4().hex,
                         "attempt_number": retry + 1, "started_utc": now(),
                         "row_index": item["row_index"], "condition": condition,
                         "pair": item["pair"], "gold": item["gold"],
                         "evidence_sha256": digest(evidence.encode()),
                         "messages": build_messages(item["claim"], evidence),
                         "server_instance": metadata["instance_id"]}
                append(events_path, event)
                interrupted = False
                try:
                    result = judge.judge(item["claim"], evidence, seed=SEED)
                    verified, citations = citation_check(result, passages)
                    result.update(citation_verified=verified, citations=citations,
                                  passages=passages, evidence_condition=condition)
                except KeyboardInterrupt:
                    result = {"label": None, "error": "interrupted_outcome_unknown"}
                    interrupted = True
                except Exception as exc:
                    result = {"label": None, "error": "experiment_error:" + type(exc).__name__}
                pred = result.get("label") if not result.get("error") else None
                record = dict(event, result=result, pred=pred, correct=pred == item["gold"],
                              finished_utc=now(), status="interrupted" if interrupted else
                              "completed" if pred in CODE_TO_LABEL.values() else "failed")
                append(predictions_path, record)
                records.append(record)
                write_outputs(directory, plan, records, "INTERRUPTED" if interrupted else "RUNNING")
                print(f"[{position}/{len(pending)}] row {item['row_index']} {condition}: {record['status']}", flush=True)
                if interrupted:
                    return 130
                transient = str(result.get("error", "")).startswith("endpoint_or_tokenisation_error:")
                if record["status"] == "completed" or not transient or retry == args.retries:
                    break
        latest = latest_by_key(records)
        status = "COMPLETE" if len(latest) == len(plan["items"]) * len(CONDITIONS) and all(
            r["status"] == "completed" for r in latest.values()) else "COMPLETE_WITH_ERRORS"
        write_outputs(directory, plan, records, status)
        return 0 if status == "COMPLETE" else 1


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("freeze", "validate", "dry-run", "run"))
    ap.add_argument("--annotations", type=Path, default=ANNOTATIONS)
    ap.add_argument("--plan", type=Path, default=PLAN)
    ap.add_argument("--out", type=Path, default=OUTPUT)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080")
    ap.add_argument("--context", type=int, default=81920)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--live", action="store_true")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    if not 0 <= args.retries <= 2 or args.context != 81920 or not 0 < args.timeout <= 600:
        raise SystemExit("context must be 81920; retries must be 0-2; timeout must be 1-600")
    if args.retry_failed and not args.resume:
        raise SystemExit("--retry-failed requires --resume")
    if args.mode != "run" and (args.live or args.resume or args.retry_failed):
        raise SystemExit("--live and resume options apply only to run")
    try:
        if args.mode == "freeze":
            if args.plan.exists():
                raise ValueError("Plan already exists; refusing to overwrite the frozen plan")
            write_json(args.plan, build_plan(args.annotations))
            print("Frozen plan written: " + str(args.plan))
            return 0
        if args.mode == "validate":
            plan, _, approval = validate_plan(args.plan, args.annotations)
            report = {"schema": SCHEMA, "status": "PASS", "validated_utc": now(),
                      "cases": len(plan["items"]), "conditions": list(CONDITIONS),
                      "planned_calls": len(plan["items"]) * len(CONDITIONS),
                      "approval": approval, "C_D_only_order": all(
                          item["C_D_identity"]["same_passage_multiset"]
                          and item["C_D_identity"]["same_passage_count"]
                          and item["C_D_identity"]["same_sum_of_passage_chars"]
                          for item in plan["items"]),
                      "source_quotations_and_offsets_verified": True,
                      "inference_calls": 0}
            if args.report:
                if args.report.exists():
                    raise ValueError("Validation report already exists")
                write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.mode == "dry-run":
            return dry_run(args)
        return run_live(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
