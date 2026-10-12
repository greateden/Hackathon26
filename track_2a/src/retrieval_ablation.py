"""Opt-in three-arm retrieval ablation for the specified-booklet task.

This module is deliberately separate from ``booklet_app.py`` and the official
``make run`` path.  Gold references are used only by ``dry-run`` for offline
retrieval measurement; they never enter a retrieval query or model prompt.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys
import time
import unicodedata
import uuid

import numpy as np

from booklet_app import (MLX_MODEL, SYSTEM_PROMPT, BookletRetriever, build_messages, classify,
                         digest, evidence_payload, load_booklet, passages)
from config import EMBEDDING_MODEL, PROJECT_ROOT
from eval_e2e import ref_probes
from eval_nli import DEFAULT_DATA, load_rows
from eval_paired import coverage
from experiment_runner import (ENCODER_REVISION, append, connect, endpoint,
                               fingerprint, locked, make_retriever, now,
                               output_path, read_log, summarise_records,
                               write_json)
from fetch_booklets import pdf_path
from hybrid_retrieval import BM25, norm_text, rrf_fuse
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION
from serve_experiments import REVISION, snapshot_info


SCHEMA = "hackapertus-retrieval-ablation-v1"
PLAN = PROJECT_ROOT / "docs/evidence/retrieval_ablation_plan_20261012.json"
OUTPUT = PROJECT_ROOT / "data/experiments/retrieval-ablation-v1"
ARMS = ("A_dense_baseline", "B_hybrid_rrf", "C_hybrid_proposition")
TOP_K = 5
CANDIDATE_K = 20
RRF_K = 60.0
SEED = 20261011


ACTORS = {
    "government": ("bundesrat", "conseil federal", "consiglio federale", "governo"),
    "parliament": ("parlament", "parlement", "parlamento", "assemblee federale"),
    "committee": ("komitee", "comite", "comitato", "referendumskomitee",
                  "comite referendaire", "comitato referendario"),
    "proponents": ("initiativkomitee", "auteurs de l initiative", "promotori dell iniziativa"),
}
NEGATION = ("nicht", "kein", "ohne", "weder", "pas", "ne ", "aucun", "sans",
            "non", "nessun", "senza")
CONDITIONS = ("wenn", "falls", "sofern", "nur wenn", "si ", "lorsque", "a condition",
              "qualora", "se ", "a condizione")
EXCEPTIONS = ("ausser", "ausgenommen", "jedoch", "sauf", "exception", "toutefois",
              "eccetto", "salvo", "tuttavia")
STOPWORDS = frozenset("der die das den dem des ein eine einer und oder von für mit auf im in zu zur zum ist sind wird werden de la le les un une des du et ou pour avec dans sur est sont sera seront il lo gli i un una e o per con nel nella è sono sarà saranno".split())


def normal(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "").casefold()).strip()


def terms(text):
    return {token for token in norm_text(text).split() if len(token) >= 4 and token not in STOPWORDS}


def quantities(text):
    value = unicodedata.normalize("NFKC", text or "").casefold()
    return set(re.findall(r"\b\d+(?:[.,]\d+)?(?:\s*(?:%|prozent|pour cent|per cento|franken|francs?|milliard\w*|million\w*))?", value))


def entities(text):
    values = set(re.findall(r"\b(?:[A-ZÄÖÜÀ-Ý][\wÀ-ÿ-]{2,}|[A-Z]{2,})\b", text or ""))
    return {normal(value) for value in values if normal(value) not in STOPWORDS}


def actor_categories(text):
    value = norm_text(text)
    return {category for category, markers in ACTORS.items()
            if any(norm_text(marker) in value for marker in markers)}


def marker_present(text, markers):
    value = " " + norm_text(text) + " "
    return any(norm_text(marker) in value for marker in markers)


def proposition_features(claim, passage, vote=""):
    """Explainable, label-agnostic features; no gold fields are accepted."""
    text = passage["text"]
    claim_terms, passage_terms = terms(claim), terms(text)
    vote_terms = terms(vote)
    claim_quantities, passage_quantities = quantities(claim), quantities(text)
    claim_entities, passage_entities = entities(claim), entities(text)
    claim_actors, passage_actors = actor_categories(claim), actor_categories(text)
    neg_claim, neg_text = marker_present(claim, NEGATION), marker_present(text, NEGATION)
    cond_claim, cond_text = marker_present(claim, CONDITIONS), marker_present(text, CONDITIONS)
    exc_claim, exc_text = marker_present(claim, EXCEPTIONS), marker_present(text, EXCEPTIONS)
    return {
        "proposal_term_coverage": len(vote_terms & passage_terms) / max(1, len(vote_terms)),
        "claim_term_coverage": len(claim_terms & passage_terms) / max(1, len(claim_terms)),
        "entity_coverage": len(claim_entities & passage_entities) / max(1, len(claim_entities)),
        "quantity_coverage": len(claim_quantities & passage_quantities) / max(1, len(claim_quantities)),
        "actor_match": bool(claim_actors and claim_actors & passage_actors),
        "actor_mismatch": bool(claim_actors and passage_actors and not claim_actors & passage_actors),
        "negation_match": neg_claim == neg_text,
        "negation_mismatch": neg_claim != neg_text,
        "condition_match": bool(cond_claim and cond_text),
        "condition_mismatch": bool(cond_claim != cond_text),
        "exception_match": bool(exc_claim and exc_text),
        "exception_mismatch": bool(exc_claim != exc_text),
    }


def feature_score(features):
    return (1.25 * features["proposal_term_coverage"]
            + 1.0 * features["claim_term_coverage"]
            + 1.0 * features["entity_coverage"]
            + 2.0 * features["quantity_coverage"]
            + 1.0 * features["actor_match"] - 0.75 * features["actor_mismatch"]
            + 0.5 * features["negation_match"] - 1.0 * features["negation_mismatch"]
            + 0.75 * features["condition_match"] - 0.75 * features["condition_mismatch"]
            + 0.5 * features["exception_match"] - 0.5 * features["exception_mismatch"])


def signature(claim, passage):
    text = passage["text"]
    return (entities(claim) & entities(text)
            | quantities(claim) & quantities(text)
            | actor_categories(claim) & actor_categories(text)
            | ({"negation"} if marker_present(text, NEGATION) else set())
            | ({"condition"} if marker_present(text, CONDITIONS) else set())
            | ({"exception"} if marker_present(text, EXCEPTIONS) else set()))


def jaccard(a, b):
    a, b = terms(a), terms(b)
    return len(a & b) / max(1, len(a | b))


def select_complementary(claim, ranked, top_k=TOP_K):
    """Greedy top-k: retain rank quality while rewarding new propositions."""
    selected, remaining, covered = [], list(ranked), set()
    while remaining and len(selected) < top_k:
        def utility(item):
            passage, score = item
            new = signature(claim, passage) - covered
            duplicate = max((jaccard(passage["text"], prior[0]["text"])
                             for prior in selected), default=0.0)
            return score + 0.01 * len(new) - 0.005 * duplicate
        best = max(range(len(remaining)), key=lambda i: (utility(remaining[i]), -i))
        item = remaining.pop(best)
        selected.append(item)
        covered.update(signature(claim, item[0]))
    return selected


class ExperimentalRetriever:
    """Three arms sharing one dense index and the unchanged Arm-A ranking."""
    def __init__(self, encoder=None):
        self.encoder = encoder
        self.indices = {}
        self.rank_cache = {}

    def _index(self, booklet):
        from retriever import LANG_TO_ADAPTER, Retriever
        key = (booklet["sha256"], booklet["language"])
        if key not in self.indices:
            if self.encoder is None:
                self.encoder = Retriever()
            records = passages(booklet)
            adapter = LANG_TO_ADAPTER[booklet["language"]]
            matrix = self.encoder.encode([record["text"] for record in records], lang_code=adapter)
            bm25 = BM25([record["text"] for record in records], norm_docs=True)
            self.indices[key] = records, matrix, bm25, adapter
        return self.indices[key]

    def rankings(self, booklet, claim, vote=""):
        from retriever import cosine_sim_matrix
        cache_key = (booklet["sha256"], booklet["language"], claim, vote)
        if cache_key in self.rank_cache:
            return self.rank_cache[cache_key]
        index_started = time.perf_counter()
        records, matrix, bm25, adapter = self._index(booklet)
        index_s = time.perf_counter() - index_started
        dense_started = time.perf_counter()
        query = self.encoder.encode([claim], lang_code=adapter)
        sims = cosine_sim_matrix(query, matrix)
        dense_order = np.argsort(-sims, kind="stable")[:CANDIDATE_K]
        dense = [(int(i), float(sims[i])) for i in dense_order]
        dense_s = time.perf_counter() - dense_started
        hybrid_started = time.perf_counter()
        lexical = bm25.top_k(claim, CANDIDATE_K)
        fused = rrf_fuse([dense, lexical], RRF_K)
        hybrid_s = time.perf_counter() - hybrid_started
        by_id = {record["id"]: record for record in records}

        def materialise(ranking, score_name):
            result = []
            for index, score in ranking:
                record = dict(records[index], source=booklet["source"], score=float(score))
                record["retrieval_score_type"] = score_name
                result.append(record)
            return result

        arm_a = materialise(dense, "cosine")
        arm_b = materialise(fused[:CANDIDATE_K], "rrf")
        rerank_started = time.perf_counter()
        reranked = []
        for rank, record in enumerate(arm_b, 1):
            feats = proposition_features(claim, record, vote)
            score = float(record["score"]) + 0.01 * feature_score(feats)
            enriched = dict(record, proposition_features=feats,
                            hybrid_rank=rank, rerank_score=score)
            reranked.append((enriched, score))
        reranked.sort(key=lambda item: (-item[1], item[0]["hybrid_rank"]))
        arm_c = [item[0] for item in select_complementary(claim, reranked, CANDIDATE_K)]
        rerank_s = time.perf_counter() - rerank_started
        result = {ARMS[0]: arm_a, ARMS[1]: arm_b, ARMS[2]: arm_c,
                  "candidate_ids": {"dense": [records[i]["id"] for i, _ in dense],
                                    "lexical": [records[i]["id"] for i, _ in lexical],
                                    "union": list(dict.fromkeys(
                                        [records[i]["id"] for i, _ in dense + lexical]))},
                  "retrieval_timings_s": {
                      ARMS[0]: index_s + dense_s,
                      ARMS[1]: index_s + dense_s + hybrid_s,
                      ARMS[2]: index_s + dense_s + hybrid_s + rerank_s,
                  },
                  "records_by_id": by_id}
        self.rank_cache[cache_key] = result
        return result

    def retrieve(self, booklet, claim, top_k=TOP_K, arm=ARMS[0], vote=""):
        return self.rankings(booklet, claim, vote)[arm][:top_k]


class ArmView:
    def __init__(self, retriever, arm, vote):
        self.retriever, self.arm, self.vote = retriever, arm, vote

    def retrieve(self, booklet, claim, top_k=TOP_K):
        return self.retriever.retrieve(booklet, claim, top_k, self.arm, self.vote)


def sufficiency_diagnostics(claim, selected):
    joined = "\n".join(record["text"] for record in selected)
    claim_entities, evidence_entities = entities(claim), entities(joined)
    claim_quantities, evidence_quantities = quantities(claim), quantities(joined)
    additions, covered = 0, set()
    for record in selected:
        current = signature(claim, record)
        if current - covered:
            additions += 1
        covered.update(current)
    provenance = [{"id": r.get("id"), "page": r.get("page"), "source": r.get("source"),
                   "pdf_sha256": r.get("pdf_sha256"), "chars": len(r.get("text", ""))}
                  for r in selected]
    return {
        "indicator_only_not_probability": True,
        "potential_missing_entities": sorted(claim_entities - evidence_entities),
        "potential_missing_quantities": sorted(claim_quantities - evidence_quantities),
        "potential_negation_mismatch": marker_present(claim, NEGATION) != marker_present(joined, NEGATION),
        "potential_condition_mismatch": marker_present(claim, CONDITIONS) != marker_present(joined, CONDITIONS),
        "potential_exception_mismatch": marker_present(claim, EXCEPTIONS) != marker_present(joined, EXCEPTIONS),
        "complementary_passages": additions,
        "several_complementary_passages": additions >= 2,
        "evidence_chars": len(joined),
        "passage_count": len(selected),
        "provenance": provenance,
    }


def locate_reference(reference, records):
    """Return gold passage IDs and distinguish exact/probe/approximate matching."""
    ref = norm_text(reference)
    normalised = {record["id"]: norm_text(record["text"]) for record in records}
    exact = [key for key, text in normalised.items() if ref and ref in text]
    if exact:
        return exact, "exact_full_reference"
    probes = [probe for probe in ref_probes(ref) if len(probe) >= 30]
    probe_hits = [key for key, text in normalised.items() if any(probe in text for probe in probes)]
    if probe_hits:
        return probe_hits, "exact_probe"
    shingles = [ref[i:i + 40] for i in range(0, len(ref) - 39, 40)]
    counts = {key: sum(shingle in text for shingle in shingles)
              for key, text in normalised.items()}
    best = max(counts.values(), default=0)
    if not shingles or best / len(shingles) < 0.5:
        return [], "not_located"
    return [key for key, count in counts.items() if count / len(shingles) >= 0.3], "approximate_shingle"


def rank_hit(ranking, gold_ids, k):
    return bool(set(record["id"] for record in ranking[:k]) & set(gold_ids))


def retrieval_audit(items, booklets, retriever):
    rows = []
    for item in items:
        request = item["request"]
        booklet = booklets[(request["booklet"], request["booklet_language"])]
        ranked = retriever.rankings(booklet, request["claim"], request["vote"])
        all_records = list(ranked["records_by_id"].values())
        gold_ids, match_method = locate_reference(item["reference"], all_records)
        arm_hits = {arm: {str(k): rank_hit(ranked[arm], gold_ids, k)
                          for k in (5, 10, 20)} for arm in ARMS}
        dense20 = arm_hits[ARMS[0]]["20"]
        if not gold_ids:
            failure = "reference_not_located_in_extracted_booklet"
        elif arm_hits[ARMS[0]]["5"]:
            failure = "selected_top5"
        elif dense20:
            failure = "ranking_depth_failure"
        else:
            failure = "initial_dense_retrieval_failure"
        union_hit = bool(set(ranked["candidate_ids"]["union"]) & set(gold_ids))
        rows.append({"row_index": item["row_index"], "pair": item["pair"],
                     "gold_label": item["gold"], "reference_match": match_method,
                     "reference_gold_passage_ids": gold_ids, "arm_hits": arm_hits,
                     "baseline_failure_stage": failure,
                     "hybrid_candidate_union_hit_at_40": union_hit,
                     "diagnostics": {arm: sufficiency_diagnostics(request["claim"], ranked[arm][:TOP_K])
                                     for arm in ARMS},
                     "selected_ids": {arm: [r["id"] for r in ranked[arm][:TOP_K]] for arm in ARMS}})
    located = [row for row in rows if row["reference_gold_passage_ids"]]
    summary = {"schema": SCHEMA, "n": len(rows), "reference_located": len(located),
               "reference_not_located": len(rows) - len(located), "denominator": "located references only",
               "arms": {}, "baseline_failure_stages": dict(Counter(r["baseline_failure_stage"] for r in rows)),
               "hybrid_candidate_union_recall_at_40": (sum(r["hybrid_candidate_union_hit_at_40"] for r in located) / len(located)
                                                        if located else None),
               "rows": rows}
    for arm in ARMS:
        summary["arms"][arm] = {"recall_at_" + str(k):
            (sum(row["arm_hits"][arm][str(k)] for row in located) / len(located) if located else None)
            for k in (5, 10, 20)}
    return summary


def validate_plan(plan, rows, data_path):
    if plan.get("schema") != SCHEMA or plan.get("dataset_sha256") != digest(data_path.read_bytes()):
        raise ValueError("Frozen plan schema or dataset hash mismatch")
    indices = plan.get("plan", {}).get("row_indices", [])
    if len(indices) != 81 or len(indices) != len(set(indices)):
        raise ValueError("Frozen plan must contain 81 unique rows")
    selected = [rows[i] for i in indices]
    pairs = Counter(row["claim_language"] + "->" + row["reference_language"] for row in selected)
    labels = Counter(str(row["entailment_label"]) for row in selected)
    groups = {(row["booklet_url"], normal(row["vote"])) for row in selected}
    booklets = Counter(row["booklet_url"] for row in selected)
    if len(pairs) != 9 or set(pairs.values()) != {9} or labels != Counter({"0": 27, "1": 27, "2": 27}):
        raise ValueError("Frozen plan language/label balance mismatch")
    if len(groups) != 81 or max(booklets.values()) > 2:
        raise ValueError("Frozen plan booklet/vote grouping mismatch")
    excluded = set(plan["exclusions"]["row_indices"])
    if excluded & set(indices):
        raise ValueError("Frozen plan includes an excluded pilot row")
    parent = list(range(len(rows)))
    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value
    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left
    seen = {}
    for index, row in enumerate(rows):
        for key in (("claim", normal(row["claim"])),
                    ("reference", normal(row["reference_string"]))):
            if key in seen:
                union(index, seen[key])
            else:
                seen[key] = index
    blocked_components = {find(index) for index in excluded}
    if any(find(index) in blocked_components for index in indices):
        raise ValueError("Frozen plan overlaps an excluded content component")
    for name, expected in plan["exclusions"].get("source_sha256", {}).items():
        path = PROJECT_ROOT / name
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError("Exclusion source changed: " + name)
    return indices


def prepare(args):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    rows = load_rows(args.data)
    plan = json.loads(args.plan.read_text())
    indices = validate_plan(plan, rows, args.data)
    issues, booklets, items = [], {}, []
    for index in indices:
        row = rows[index]
        request = {"claim": row["claim"], "claim_language": row["claim_language"],
                   "booklet": row["booklet_url"], "booklet_language": row["reference_language"],
                   "vote": row["vote"]}
        key = request["booklet"], request["booklet_language"]
        if key not in booklets:
            path = pdf_path(key[0])
            if not path.is_file():
                issues.append("Missing cached PDF for row " + str(index))
                continue
            booklet = load_booklet(str(path), key[1])
            booklet["source"] = key[0]
            booklets[key] = booklet
        items.append({"row_index": index, "request": request,
                      "pair": row["claim_language"] + "->" + row["reference_language"],
                      "gold": CODE_TO_LABEL[row["entailment_label"]],
                      "reference": row["reference_string"],
                      "group": {"booklet_url": row["booklet_url"], "vote": row["vote"]}})
    encoder_path = None
    try:
        from huggingface_hub import snapshot_download
        encoder_path = Path(snapshot_download(EMBEDDING_MODEL, revision=ENCODER_REVISION,
                                              local_files_only=True))
    except Exception as exc:
        issues.append("Cached encoder unavailable: " + type(exc).__name__)
    model_info = {}
    try:
        _, model_info = snapshot_info()
    except Exception as exc:
        issues.append("Cached Apertus checkpoint unavailable: " + type(exc).__name__)
    source_names = ("retrieval_ablation.py", "booklet_app.py", "experiment_runner.py",
                    "hybrid_retrieval.py", "retriever.py", "labels.py")
    source_hashes = {"src/" + name: digest((PROJECT_ROOT / "src" / name).read_bytes())
                     for name in source_names}
    config = {"model": MLX_MODEL, "model_revision": REVISION, "encoder": EMBEDDING_MODEL,
              "encoder_revision": ENCODER_REVISION, "arms": list(ARMS), "top_k": TOP_K,
              "candidate_k": CANDIDATE_K, "rrf_k": RRF_K, "temperature": 0,
              "seed": SEED, "max_tokens": 512, "context_tokens": args.context,
              "parser_version": LABEL_PARSE_VERSION,
              "system_prompt_sha256": digest(SYSTEM_PROMPT.encode()),
              "only_variable": "retrieval/evidence selection"}
    contract = {"schema": SCHEMA, "dataset_sha256": plan["dataset_sha256"],
                "plan_sha256": digest(args.plan.read_bytes()), "plan": plan["plan"],
                "configuration": config, "source_sha256": source_hashes,
                "invariants": {"same_cases": True, "same_model": True, "same_prompt": True,
                               "same_decoding": True, "five_passages_per_arm": True,
                               "reference_available_to_inference": False},
                "items": [{k: v for k, v in item.items() if k != "reference"} for item in items],
                "model_cache": model_info}
    return {"status": "BLOCKED" if issues else "PASS", "issues": issues,
            "contract": contract, "items": items, "booklets": booklets,
            "encoder_path": encoder_path, "planned_calls": len(items) * len(ARMS)}


def make_experimental_retriever(snapshot):
    baseline = make_retriever(snapshot)
    return ExperimentalRetriever(encoder=baseline.encoder)


def write_dry_run(directory, prepared, audit):
    manifest = {"schema": SCHEMA, "status": "DRY_RUN", "created_utc": now(),
                "contract_sha256": fingerprint(prepared["contract"]),
                "contract": prepared["contract"], "inference_calls": 0,
                "note": "Offline retrieval executed; no model endpoint was contacted."}
    write_json(directory / "manifest.json", manifest)
    write_json(directory / "retrieval_audit.json", audit)
    (directory / "predictions.jsonl").touch(exist_ok=True)
    write_json(directory / "summary.json", {"schema": SCHEMA, "status": "DRY_RUN",
        "planned_calls": prepared["planned_calls"], "inference_calls": 0,
        "retrieval_audit": {k: v for k, v in audit.items() if k != "rows"}})
    with (directory / "paired_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow(["row_index", "pair", "gold", *ARMS])
    (directory / "error_analysis.md").write_text(
        "# Retrieval ablation error analysis\n\nDry run only: no model predictions exist. "
        "See `retrieval_audit.json` for exact/probe/approximate reference matching and failure stages.\n")


def exact_sign_test(wins, losses):
    n = wins + losses
    if not n:
        return None
    tail = sum(math.comb(n, i) for i in range(0, min(wins, losses) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def wilson_interval(successes, total, z=1.959963984540054):
    if not total:
        return [None, None]
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / total
                         + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def paired_stats(left, right, latest):
    wins = losses = ties = 0
    for item in left:
        a = latest.get(str(item["row_index"]) + ":" + right[0])
        b = latest.get(str(item["row_index"]) + ":" + right[1])
        if not a or not b:
            continue
        if a["correct"] == b["correct"]:
            ties += 1
        elif b["correct"]:
            wins += 1
        else:
            losses += 1
    discordant = wins + losses
    return {"left": right[0], "right": right[1], "right_wins": wins,
            "right_losses": losses, "ties": ties,
            "right_win_rate_among_discordant": wins / discordant if discordant else None,
            "right_win_rate_wilson_95": wilson_interval(wins, discordant),
            "exact_two_sided_sign_p": exact_sign_test(wins, losses)}


def render_outputs(directory, manifest, records, status):
    latest = {record["key"]: record for record in records}
    planned = len(manifest["contract"]["items"]) * len(ARMS)
    summary = {"schema": SCHEMA, "status": status, "updated_utc": now(),
               "planned": planned, "attempts": len(records),
               "completed": sum(record.get("status") == "completed" for record in latest.values()),
               "failed": sum(record.get("status") != "completed" for record in latest.values()),
               "missing": planned - len(latest),
               "methods": {}, "accuracy_by_language_pair": {},
               "paired": [], "citation_note": "verification proves textual provenance, not semantic sufficiency"}
    for arm in ARMS:
        arm_rows = [r for r in latest.values() if r["arm"] == arm]
        stats = summarise_records(arm_rows) if arm_rows else {"n": 0, "accuracy": None, "macro_f1": None}
        stats["citation_verified"] = sum((r.get("result") or {}).get("citation_verified") is True for r in arm_rows)
        summary["methods"][arm] = stats
        pair_stats = {}
        for pair in sorted({r["pair"] for r in arm_rows}):
            subset = [r for r in arm_rows if r["pair"] == pair]
            pair_stats[pair] = summarise_records(subset)
        summary["accuracy_by_language_pair"][arm] = pair_stats
    for pair in ((ARMS[0], ARMS[1]), (ARMS[0], ARMS[2]), (ARMS[1], ARMS[2])):
        summary["paired"].append(paired_stats(manifest["contract"]["items"], pair, latest))
    audit_path = directory / "retrieval_audit.json"
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text())
        summary["retrieval_audit"] = {k: v for k, v in audit.items() if k != "rows"}
    write_json(directory / "summary.json", summary)
    with (directory / "paired_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["row_index", "pair", "gold"] + [value for arm in ARMS for value in (arm + "_pred", arm + "_correct", arm + "_input_tokens", arm + "_latency_s", arm + "_citation_verified")])
        for item in manifest["contract"]["items"]:
            row = [item["row_index"], item["pair"], item["gold"]]
            for arm in ARMS:
                record = latest.get(str(item["row_index"]) + ":" + arm, {})
                result = record.get("result") or {}
                usage = result.get("usage") or {}
                row += [record.get("pred"), record.get("correct"), usage.get("prompt_tokens"),
                        record.get("elapsed_s"), result.get("citation_verified")]
            writer.writerow(row)
    failures = Counter()
    for record in latest.values():
        if record.get("status") != "completed":
            failures["inference_or_parse_error"] += 1
        diagnostics = record.get("evidence_diagnostics") or {}
        if diagnostics.get("potential_missing_entities"):
            failures["potential_missing_entities"] += 1
        if diagnostics.get("potential_missing_quantities"):
            failures["potential_missing_quantities"] += 1
        for name in ("potential_negation_mismatch", "potential_condition_mismatch", "potential_exception_mismatch"):
            if diagnostics.get(name):
                failures[name] += 1
    lines = ["# Retrieval ablation error analysis", "", "Heuristic flags are diagnostics, not calibrated probabilities or label overrides.", "",
             "## Typical recorded categories", ""]
    lines += [f"- {name}: {count}" for name, count in sorted(failures.items())] or ["- No completed records yet."]
    (directory / "error_analysis.md").write_text("\n".join(lines) + "\n")
    return summary


def execute(args, prepared, audit):
    directory = output_path(args.out)
    contract = prepared["contract"]
    identity = fingerprint(contract)
    with locked(directory):
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if not args.resume or manifest.get("contract_sha256") != identity:
                raise ValueError("Run exists or contract changed; use --resume with the original contract")
        else:
            if args.resume:
                raise ValueError("Cannot resume without manifest.json")
            manifest = {"schema": SCHEMA, "created_utc": now(), "contract_sha256": identity,
                        "contract": contract, "sessions": []}
            write_json(manifest_path, manifest)
        write_json(directory / "retrieval_audit.json", audit)
        (directory / "predictions.jsonl").touch(exist_ok=True)
        records = read_log(directory / "predictions.jsonl")
        latest = {record["key"]: record for record in records}
        pending = [(item, arm) for item in prepared["items"] for arm in ARMS
                   if str(item["row_index"]) + ":" + arm not in latest or
                   (args.retry_failed and latest[str(item["row_index"]) + ":" + arm]["status"] != "completed")]
        if not pending:
            status = "COMPLETE" if all(r["status"] == "completed" for r in latest.values()) else "COMPLETE_WITH_ERRORS"
            render_outputs(directory, manifest, records, status)
            return 0 if status == "COMPLETE" else 1
        judge, metadata = connect(args)
        for key in ("config_sha256", "shards", "mlx_lm_version", "quantisation"):
            if metadata[key] != contract["model_cache"][key]:
                raise ValueError("Loaded model differs from frozen preflight provenance")
        manifest["sessions"].append({"started_utc": now(), "endpoint": metadata})
        write_json(manifest_path, manifest)
        retriever = make_experimental_retriever(prepared["encoder_path"])
        for position, (item, arm) in enumerate(pending, 1):
            key = str(item["row_index"]) + ":" + arm
            for retry in range(args.retries + 1):
                event = {"schema": SCHEMA, "key": key, "attempt_id": uuid.uuid4().hex,
                         "attempt_number": retry + 1, "started_utc": now(),
                         "row_index": item["row_index"], "arm": arm,
                         "gold": item["gold"], "pair": item["pair"], "input": item["request"],
                         "server_instance": metadata["instance_id"]}
                append(directory / "events.jsonl", event)
                started = time.perf_counter()
                interrupted = False
                try:
                    request = dict(item["request"], evidence="retrieved", top_k=TOP_K)
                    booklet = prepared["booklets"][(request["booklet"], request["booklet_language"])]
                    ranked = retriever.rankings(booklet, request["claim"], request["vote"])
                    result = classify(request, judge, ArmView(retriever, arm, request["vote"]), booklet, seed=SEED)
                    result["retrieval_s"] = ranked["retrieval_timings_s"][arm]
                    selected = result["passages"]
                    event["messages"] = build_messages(request["claim"], evidence_payload(booklet, selected))
                    event["evidence_chars"] = len(evidence_payload(booklet, selected))
                    event["reference_shingle_coverage"] = coverage(item["reference"], selected)
                    diagnostics = sufficiency_diagnostics(request["claim"], selected)
                except KeyboardInterrupt:
                    result = {"label": None, "error": "interrupted_outcome_unknown"}
                    diagnostics = {}
                    interrupted = True
                except Exception as exc:
                    result = {"label": None, "error": "pipeline_error:" + type(exc).__name__}
                    diagnostics = {}
                pred = result.get("label") if not result.get("error") else None
                record = dict(event, result=result, pred=pred, correct=pred == item["gold"],
                              evidence_diagnostics=diagnostics, elapsed_s=time.perf_counter() - started,
                              finished_utc=now(), status="interrupted" if interrupted else
                              "completed" if pred in CODE_TO_LABEL.values() else "failed")
                append(directory / "predictions.jsonl", record)
                records.append(record)
                render_outputs(directory, manifest, records, "INTERRUPTED" if interrupted else "RUNNING")
                print(f"[{position}/{len(pending)}] row {item['row_index']} {arm}: {record['status']}", flush=True)
                if interrupted:
                    return 130
                error = result.get("error", "")
                transient = error.startswith("endpoint_or_tokenisation_error:")
                if record["status"] == "completed" or not transient or retry == args.retries:
                    break
        latest = {record["key"]: record for record in records}
        status = "COMPLETE" if len(latest) == len(contract["items"]) * len(ARMS) and all(
            record["status"] == "completed" for record in latest.values()) else "COMPLETE_WITH_ERRORS"
        render_outputs(directory, manifest, records, status)
        return 0 if status == "COMPLETE" else 1


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("preflight", "dry-run", "run"))
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--plan", type=Path, default=PLAN)
    ap.add_argument("--out", type=Path, default=OUTPUT)
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080")
    ap.add_argument("--context", type=int, default=81920)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    if not 512 < args.context <= 262144 or not 0 < args.timeout <= 600 or not 0 <= args.retries <= 2:
        raise SystemExit("invalid context, timeout or retries (retries must be 0-2)")
    if args.retry_failed and not args.resume:
        raise SystemExit("--retry-failed requires --resume")
    if args.mode != "run" and (args.resume or args.retry_failed):
        raise SystemExit("resume options apply only to run")
    if endpoint(args.endpoint) not in ("http://127.0.0.1:8080", "http://localhost:8080"):
        raise SystemExit("native experiment endpoint must be loopback")
    try:
        prepared = prepare(args)
        args.out = output_path(args.out)
        write_json(args.out / "preflight.json", {k: v for k, v in prepared.items()
                                                  if k not in ("items", "booklets", "encoder_path")})
        print(f"Preflight {prepared['status']}: {prepared['planned_calls']} planned calls")
        for issue in prepared["issues"]:
            print("- " + issue)
        if prepared["issues"]:
            return 2
        if args.mode == "preflight":
            print("No encoder inference, endpoint call, model load or download was attempted.")
            return 0
        retriever = make_experimental_retriever(prepared["encoder_path"])
        audit = retrieval_audit(prepared["items"], prepared["booklets"], retriever)
        if args.mode == "dry-run":
            write_dry_run(args.out, prepared, audit)
            print("DRY_RUN: offline retrieval complete; inference calls = 0")
            return 0
        return execute(args, prepared, audit)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print("BLOCKED: " + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
