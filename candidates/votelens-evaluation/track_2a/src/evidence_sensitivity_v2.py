"""Standalone evidence sufficiency and order-sensitivity diagnostic.

``freeze``, ``validate`` and ``dry-run`` are offline.  ``run`` is the only mode
that can contact an endpoint, and additionally requires ``--live`` plus recorded independent
ChatGPT confirmation of the AI-assisted annotations.  Production retrieval and submission entry points
are not imported or modified beyond reusing their prompt/client contracts.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
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


SCHEMA = "hackapertus-evidence-sensitivity-v2"
ANNOTATION_SCHEMA = "hackapertus-evidence-sensitivity-annotations-v2"
ANNOTATIONS = PROJECT_ROOT / "docs/evidence/evidence_sensitivity_annotations_v2_20261012.json"
PLAN = PROJECT_ROOT / "docs/evidence/evidence_sensitivity_plan_v2_20261012.json"
SOURCE = PROJECT_ROOT / "data/experiments/retrieval-ablation-v1"
OUTPUT = PROJECT_ROOT / "data/experiments/evidence-sensitivity-v2"
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
    """Bind scientific decisions and exclusions; only external review may change."""
    review_fields = {"overall_status", "reviewer", "reviewed_utc", "review_note"}
    spec = {k: v for k, v in annotation.items() if k not in review_fields | {"cases"}}
    spec["cases"] = [{k: v for k, v in c.items()
                      if k not in {"review_decision", "reviewer_note"}}
                     for c in annotation.get("cases", [])]
    return spec


def annotation_spec_sha256(annotation):
    return fingerprint(annotation_spec(annotation))


def approval_status(annotation):
    cases = annotation.get("cases", [])
    decisions = Counter(c.get("review_decision") for c in cases)
    retained = [c for c in cases if c.get("primary_analysis") is True]
    approved = (bool(retained)
                and annotation.get("overall_status") == "confirmed_by_independent_chatgpt"
                and annotation.get("review_kind") == "AI-assisted independent evidence adjudication"
                and all(c.get("review_decision") == "approved" for c in retained)
                and all(c.get("review_decision") == "excluded" for c in cases if not c.get("primary_analysis"))
                and isinstance(annotation.get("reviewer"), str) and annotation["reviewer"].strip()
                and isinstance(annotation.get("reviewed_utc"), str) and annotation["reviewed_utc"].strip())
    return {"approved": bool(approved), "overall_status": annotation.get("overall_status"),
            "decisions": dict(decisions), "reviewer": annotation.get("reviewer"),
            "reviewed_utc": annotation.get("reviewed_utc"),
            "review_kind": annotation.get("review_kind"), "human_verification": False}


def source_paths():
    return [DEFAULT_DATA, SOURCE / "manifest.json", SOURCE / "predictions.jsonl",
            SOURCE / "summary.json", PROJECT_ROOT / "src/evidence_sensitivity.py",
            PROJECT_ROOT / "docs/evidence/evidence_sensitivity_plan_20261012.json",
            PROJECT_ROOT / "docs/evidence/evidence_sensitivity_annotations_20261012.json",
            PROJECT_ROOT / "docs/evidence/evidence_sensitivity_offline_validation_20261012.json",
            PROJECT_ROOT / "src/evidence_sensitivity_v2.py"]


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


def get_booklet(row):
    url = row["booklet_url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname == "admin.ch" or parsed.hostname.endswith(".admin.ch")):
        raise ValueError("Evidence must use the recorded official admin.ch PDF")
    booklet = load_booklet(str(pdf_path(url)), row["reference_language"])
    booklet["source"] = url
    return booklet


def reviewed_passage(booklet, spec, identity, language):
    pages = {p["page"]: p["text"] for p in booklet["pages"]}
    start, end, quote = find_span(pages[spec["page"]], spec["start"], spec["end"])
    if (spec["text"] != quote or spec["page_char_start"] != start
            or spec["page_char_end"] != end or spec["printed_page"] != spec["page"]):
        raise ValueError("Reviewed quotation, page or extraction offset mismatch")
    passage = dict(spec, id=identity, lang=language,
                   annotation_status="AI_assisted_pending_independent_review")
    verify_passage(booklet, passage)
    return passage


def verify_offsets(booklet, passage):
    verify_passage(booklet, passage)
    page = next(p["text"] for p in booklet["pages"] if p["page"] == passage["page"])
    if page[passage["page_char_start"]:passage["page_char_end"]] != passage["text"]:
        raise ValueError("Extraction offsets do not reproduce exact quotation")


def assert_block_rotation(claim, minimal, distractors, conditions):
    """Reconstruct rendered messages, including headers, before asserting identity."""
    c = conditions[CONDITIONS[2]]["passages"]
    d = conditions[CONDITIONS[3]]["passages"]
    if not minimal or len(distractors) != 2 or c != minimal + distractors or d != distractors + minimal:
        raise ValueError("C/D must move the complete B block without reversing either internal order")
    render = lambda ps: build_messages(claim, evidence_payload(None, ps))
    c_messages = render(c)
    restored = d[2:] + d[:2]
    if render(restored) != c_messages or render(d)[0] != c_messages[0]:
        raise ValueError("Rendered C/D prompts differ beyond passage-block placement")
    if len(evidence_payload(None, c)) != len(evidence_payload(None, d)):
        raise ValueError("C/D prompt character length differs")
    return {"same_passage_multiset": True, "same_passage_count": True,
            "same_sum_of_passage_chars": True, "only_order_differs": True,
            "internal_B_order_preserved": True, "internal_distractor_order_preserved": True,
            "rendered_prompt_rotation_verified": True, "same_model_settings_and_token_budget": True}


def offline_tokenizer():
    # Same loader/template as mlx-lm 0.32 server; local-only; no weights loaded.
    from functools import lru_cache
    return _cached_tokenizer()


from functools import lru_cache


@lru_cache(maxsize=1)
def _cached_tokenizer():
    from serve_experiments import snapshot_info
    from mlx_lm.tokenizer_utils import load
    snapshot, _ = snapshot_info()
    tokenizer = load(snapshot, tokenizer_config_extra={"local_files_only": True})
    files = [p for pattern in ("tokenizer*", "special_tokens_map.json", "chat_template*")
             for p in snapshot.glob(pattern) if p.is_file()]
    identities = {p.name: sha256_file(p) for p in sorted(set(files))}
    return tokenizer, identities


def prompt_tokens(messages):
    tokenizer, _ = offline_tokenizer()
    tokens = tokenizer.apply_chat_template(messages, tools=None, tokenize=True,
                                          add_generation_prompt=True, enable_thinking=False)
    return len(tokens), fingerprint(tokens)


def resolve_annotations(path):
    path = Path(path).resolve()
    if PROJECT_ROOT.resolve() not in path.parents:
        raise ValueError("Annotations must resolve inside the project root")
    return path


def build_plan(annotation_path=ANNOTATIONS):
    annotation_path = resolve_annotations(annotation_path)
    annotation, rows, source_manifest, latest = load_sources(annotation_path)
    items, adjudications = [], []
    for case in annotation["cases"]:
        index = case["row_index"]
        row = rows[index]
        booklet = get_booklet(row)
        minimal = [reviewed_passage(booklet, spec, f"row{index}-B-{number}", row["reference_language"])
                   for number, spec in enumerate(case["source_spans"], 1)]
        distractors = [reviewed_passage(booklet, spec, f"row{index}-X-{number}", row["reference_language"])
                      for number, spec in enumerate(case["distractor_spans"], 1)]
        for audit in case["distractor_audit_v1"]:
            verify_offsets(booklet, audit)
            if audit["classification"] not in {"irrelevant", "plausible_hard_negative", "corroborating", "ambiguous_or_decisive"}:
                raise ValueError("Unclassified historical distractor")
        adjudications.append(dict(row_index=index, status=case["adjudication_status"],
                                   primary_analysis=case["primary_analysis"], gold=CODE_TO_LABEL[row["entailment_label"]],
                                   claim=row["claim"], claim_language=row["claim_language"],
                                   booklet_language=row["reference_language"], note=case["adjudication_note"],
                                   source_evidence=minimal, distractor_audit_v1=case["distractor_audit_v1"],
                                   reviewed_distractors=distractors))
        if not case["primary_analysis"]:
            continue
        if len(distractors) != 2 or any(p["classification"] not in {"irrelevant", "plausible_hard_negative"} for p in distractors):
            raise ValueError("Primary C requires two non-decisive reviewed distractors")
        source_a, source_c = latest[f"{index}:A_dense_baseline"], latest[f"{index}:C_hybrid_proposition"]
        original = source_a["result"]["passages"]
        for p in original:
            verify_passage(booklet, p)
        ps = dict(zip(CONDITIONS, (original, minimal, minimal + distractors, distractors + minimal)))
        conditions = {}
        for name, evidence in ps.items():
            payload = evidence_payload(booklet, evidence)
            messages = build_messages(row["claim"], payload)
            n, token_hash = prompt_tokens(messages)
            if n + 512 > 81920:
                raise ValueError("Prompt exceeds unchanged context/completion budget")
            conditions[name] = {"passages": evidence, "messages": messages,
                                "evidence_sha256": digest(payload.encode()), "evidence_chars": len(payload),
                                "message_sha256": fingerprint(messages), "prompt_tokens_offline": n,
                                "token_ids_sha256": token_hash}
        if conditions[CONDITIONS[0]]["messages"] != source_a["messages"]:
            raise ValueError("A differs from recorded SwissBERT Top-5 prompt")
        identity = assert_block_rotation(row["claim"], minimal, distractors, conditions)
        counts = {c: conditions[c]["prompt_tokens_offline"] for c in CONDITIONS}
        identity["prompt_token_delta_D_minus_C"] = counts[CONDITIONS[3]] - counts[CONDITIONS[2]]
        items.append(dict(row_index=index, cohort=case["cohort"], claim=row["claim"],
                          claim_language=row["claim_language"], booklet_language=row["reference_language"],
                          pair=row["claim_language"] + "->" + row["reference_language"], vote=row["vote"],
                          booklet_url=row["booklet_url"], pdf_sha256=booklet["sha256"],
                          gold=CODE_TO_LABEL[row["entailment_label"]], source_A_prediction=source_a["pred"],
                          source_C_prediction=source_c["pred"], annotation={k: v for k, v in case.items() if k not in {"review_decision", "reviewer_note"}},
                          conditions=conditions, C_D_identity=identity,
                          B_C_length_confound={"prompt_token_delta_C_minus_B": counts[CONDITIONS[2]] - counts[CONDITIONS[1]],
                                               "isolated_semantic_interference": False}))
    config = source_manifest["contract"]["configuration"]
    return {"schema": SCHEMA, "created_utc": now(), "purpose": "Post-hoc diagnostic on previously observed cases, not an independent generalisation benchmark.",
            "adjudication_type": "AI-assisted independent evidence adjudication; not completed human verification",
            "selection": {"n_reviewed": len(adjudications), "n": len(items),
                          "retained": [i["row_index"] for i in items],
                          "excluded": [a["row_index"] for a in adjudications if not a["primary_analysis"]],
                          "policy": annotation["selection_policy"]}, "planned_calls": len(items) * 4,
            "annotation_binding": {"path": str(annotation_path.relative_to(PROJECT_ROOT.resolve())),
                                   "evidence_spec_sha256": annotation_spec_sha256(annotation),
                                   "approval_required_for_live": True}, "source_identities": source_identities(),
            "source_provenance": {"experiment": str(SOURCE.relative_to(PROJECT_ROOT)),
                                  "dataset": str(DEFAULT_DATA.relative_to(PROJECT_ROOT)),
                                  "dataset_sha256": sha256_file(DEFAULT_DATA)},
            "tokenizer": {"model": MLX_MODEL, "revision": REVISION, "loader": "mlx_lm.tokenizer_utils.load",
                          "chat_template_kwargs": {"enable_thinking": False},
                          "files_sha256": offline_tokenizer()[1], "weights_loaded": False,
                          "warning": "Preserves existing tokenizer behaviour, including its installed Transformers regex warning; no silent tokenizer correction. Live usage must agree with frozen token counts."},
            "inference_contract": {"model": config["model"], "revision": config["model_revision"],
                                   "temperature": config["temperature"], "seed": config["seed"],
                                   "max_tokens": config["max_tokens"], "context_tokens": config["context_tokens"],
                                   "parser_version": config["parser_version"],
                                   "system_prompt_sha256": config["system_prompt_sha256"],
                                   "chat_template_kwargs": {"enable_thinking": False},
                                   "only_intended_variable": "evidence payload"},
            "condition_definitions": dict(zip(CONDITIONS, (
                "Unchanged original recorded SwissBERT Top-5.", "Reviewed minimal decisive evidence with necessary identity, attribution and conditions.",
                "B followed by two reviewed non-decisive distractors; length-confounded contrast with B.",
                "Identical C with the complete B block after distractors; both internal orders preserved."))),
            "adjudications": adjudications, "items": items}


def validate_plan(plan_path=PLAN, annotation_path=ANNOTATIONS, require_approval=False):
    annotation_path = resolve_annotations(annotation_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    expected = build_plan(annotation_path)
    # Rebuilding offline verifies all quotations, offsets, frozen prompts, C/D rotation,
    # exclusions, dataset labels, tokenizer IDs and every bound historical source.
    actual = {k: v for k, v in plan.items() if k != "created_utc"}
    rebuilt = {k: v for k, v in expected.items() if k != "created_utc"}
    # The frozen runner hash records the preparation implementation. Operational
    # repairs must not rewrite the approved plan or break its resume identity.
    # Every scientific field and other source hash is still reconstructed exactly;
    # the executing implementation is separately recorded in each live session.
    runner_source = "src/evidence_sensitivity_v2.py"
    rebuilt["source_identities"][runner_source] = actual["source_identities"][runner_source]
    if actual != rebuilt:
        raise ValueError("Frozen v2 plan differs from its exact offline reconstruction")
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    approval = approval_status(annotation)
    if require_approval and not approval["approved"]:
        raise ValueError("pending_independent_chatgpt_review; live execution is locked")
    return plan, annotation, approval


def citation_check(result, passages):
    snippet = result.get("evidence_snippet")
    if not isinstance(snippet, str) or not snippet.strip():
        return False, []
    matches = [p for p in passages if normalise_citation(snippet) in normalise_citation(p["text"])]
    return bool(matches), matches


def scoring_record(record):
    result = record.get("result") or {}
    elapsed = record.get("elapsed_s")
    if elapsed is None:
        elapsed = result.get("elapsed_s")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Record lacks valid measured elapsed_s: " + str(record.get("key")))
    return dict(record, elapsed_s=elapsed, error=result.get("error"))


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
        scored = [scoring_record(r) for r in rows]
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
                subset = [scoring_record(r) for r in rows if r[field] == value]
                grouped[value] = summarise(subset)
            summary[target][condition] = grouped
    for left, right, name in ((CONDITIONS[0], CONDITIONS[1], "minimal_vs_original"),
                              (CONDITIONS[1], CONDITIONS[2], "added_evidence_length_confounded"),
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
        manifest["sessions"].append({"started_utc": now(), "endpoint": metadata,
                                    "runner_sha256": sha256_file(Path(__file__))})
        write_json(manifest_path, manifest)
        for position, (item, condition) in enumerate(pending, 1):
            key = f"{item['row_index']}:{condition}"
            passages = item["conditions"][condition]["passages"]
            evidence = "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in passages)
            if build_messages(item["claim"], evidence) != item["conditions"][condition]["messages"]:
                raise ValueError("Live prompt differs from frozen rendered messages")
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
                attempt_started = time.perf_counter()
                try:
                    result = judge.judge(item["claim"], evidence, seed=SEED)
                    if not result.get("error") and (result.get("usage") or {}).get("prompt_tokens") != item["conditions"][condition]["prompt_tokens_offline"]:
                        result["error"] = "frozen_prompt_token_count_mismatch"
                        result["label"] = None
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
                              elapsed_s=time.perf_counter() - attempt_started,
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
                      "reviewed_cases": len(plan["adjudications"]), "excluded_rows": plan["selection"]["excluded"], "cases": len(plan["items"]), "conditions": list(CONDITIONS),
                      "planned_calls": len(plan["items"]) * len(CONDITIONS),
                      "approval": approval, "C_D_only_order": all(
                          item["C_D_identity"]["same_passage_multiset"]
                          and item["C_D_identity"]["same_passage_count"]
                          and item["C_D_identity"]["same_sum_of_passage_chars"]
                          for item in plan["items"]),
                      "source_quotations_and_offsets_verified": True, "complete_B_block_rotation_verified": True, "offline_token_counts_verified": True,
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
