"""Evaluate the NLI judge against the official Track 2A eval set.

Data: data/eval/mnli_swiss_v1.1.jsonl (regenerate: python3 fetch_eval_data.py).
Official label codes: 0=entailment, 1=neutral, 2=contradiction (src/labels.py).

Modes:
  --evidence oracle       (default) judge receives each item's gold
                          reference_string: measures the judgement step.
  --evidence retrieve     full pipeline over the legacy 526-passage CLI
                          corpus (plumbing check only - see AGENTS.md).
  --evidence retrieve-v2  full pipeline over the 60-booklet PDF corpus via
                          main.Pipeline with retrieval forced to the booklet
                          stack - the same stack production `make run` uses.
Retrieval failures and unparseable/failed judge replies are recorded as
errors (pred=None), never defaulted to a label.

Leakage policy: dev split = seeded 60-item plumbing subset; eval split is
held out and must only be run after prompts/settings are frozen.

Usage (from src/):
    python3 eval_nli.py --split dev --limit 30
    python3 eval_nli.py --split eval --backend mlx
    python3 eval_nli.py --split dev --backend openai --evidence retrieve-v2
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (DATA_DIR, LLM_BACKEND, MLX_MODEL, OLLAMA_MODEL, TOP_K,
                    OPENAI_BASE_URL, JUDGE_MODEL, PROMPT_CONFIG)
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION, label_to_code
from nli_judge import (build_judge, get_prompt_config, PROMPT_CONFIGS)
from sampling import balanced_sample

DEFAULT_DATA = DATA_DIR / "eval" / "mnli_swiss_v1.1.jsonl"
DEV_SEED = 20261009
DEV_SIZE = 60
EVIDENCE_MAX_CHARS = 1900   # < format_evidence 2000 cap so gold evidence is
                            # not silently dropped by its per-chunk check
CLASSES = ["entailment", "neutral", "contradiction"]


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    bad = [r for r in rows if CODE_TO_LABEL.get(r.get("entailment_label")) is None
           or not r.get("reference_string")]
    if bad:
        sys.exit(f"ERROR: {len(bad)} rows have a missing/non-official label "
                 "or empty reference_string - refusing to score")
    return rows


def split_indices(n, split, seed, dev_size):
    """Deterministic seeded split; dev exists for plumbing checks only."""
    if split == "all":
        return list(range(n))
    rng = random.Random(seed)
    dev = set(rng.sample(range(n), min(dev_size, n)))
    if split == "dev":
        return sorted(dev)
    return [i for i in range(n) if i not in dev]


def overlap_with_rest(rows, idx):
    """Dev/eval contamination audit (2026-10-10, report §9). Counts how many
    selected items share surface material with the held-out remainder:
    claim, reference_string, booklet_url, the exact (claim, reference, label)
    triple, and any-overlap "cluster" membership. These fields are
    gold-labelling material - overlap means the held-out rows are not
    independent evidence. Computed offline and recorded in meta only; it
    never feeds scoring or retrieval."""
    sel = set(idx)
    rest = [rows[i] for i in range(len(rows)) if i not in sel]
    claims = Counter(r.get("claim") for r in rest if r.get("claim"))
    refs = Counter(r.get("reference_string")
                   for r in rest if r.get("reference_string"))
    urls = Counter(r.get("booklet_url") for r in rest if r.get("booklet_url"))
    triples = {(r.get("claim"), r.get("reference_string"),
                r.get("entailment_label")) for r in rest}
    n_claim = n_ref = n_url = n_tri = n_cluster = 0
    for i in idx:
        r = rows[i]
        h_c = bool(claims.get(r.get("claim")))
        h_r = bool(refs.get(r.get("reference_string")))
        h_u = bool(urls.get(r.get("booklet_url")))
        h_t = (r.get("claim"), r.get("reference_string"),
               r.get("entailment_label")) in triples
        n_claim += h_c
        n_ref += h_r
        n_url += h_u
        n_tri += h_t
        n_cluster += (h_c or h_r or h_u)
    return {"n_selected": len(idx), "n_held_out": len(rest),
            "claim_overlap": n_claim, "reference_overlap": n_ref,
            "booklet_overlap": n_url, "exact_triple_overlap": n_tri,
            "cluster_overlap": n_cluster}


def oracle_evidence(item, pconf=None):
    # Keys mirror retriever output so every judge (incl. LexicalJudge which
    # reads p["score"]) works unchanged on oracle evidence.
    text = item["reference_string"]
    if pconf and pconf.get("window"):
        text = select_window(text, item["claim"], EVIDENCE_MAX_CHARS)
    else:
        text = text[:EVIDENCE_MAX_CHARS]
    return [{"id": "gold",
             "lang": (item.get("reference_language") or "?").lower(),
             "year": "?",
             "source_file": item.get("vote", "official-eval-set"),
             "score": 1.0,
             "text": text}]


# --- claim-lexical evidence window (prompt config "select") -----------------
# The dev-run error analysis showed the 1900-char HEAD truncation cut
# decisive negation markers out of the oracle evidence (tail-only markers),
# while most of the kept head was boilerplate. select_window replaces head
# truncation with a deterministic lexical-overlap window: among contiguous
# segment runs that fit the budget, take the one with the most claim-token
# occurrences; fall back to the head when nothing overlaps (no information
# advantage). Pure Python, no model, no randomness.

_WORD_RE = re.compile(r"[0-9a-zäöüéèêëààèéïîôùûüçß']{2,}")
_SEG_SPLIT_RE = re.compile(r"(?<=\n)|(?<=[.!?;])\s+")


def _claim_token_pattern(claim):
    toks = sorted({t for t in _WORD_RE.findall(claim.lower()) if len(t) >= 4},
                  key=len, reverse=True)
    if not toks:
        return None
    return re.compile(r"(?<![\w'])(" + "|".join(map(re.escape, toks)) +
                      r")(?![\w'])", re.I)


def _segments(text):
    """Split into paragraph blocks, then into sentence-ish chunks."""
    segs = []
    for para in text.split("\n\n"):
        if len(para) <= 300:
            segs.append(para)
        else:
            segs.extend(s for s in _SEG_SPLIT_RE.split(para) if s.strip())
    return [s for s in segs if s.strip()]


def select_window(text, claim, max_chars):
    if len(text) <= max_chars:
        return text
    pat = _claim_token_pattern(claim)
    if pat is None:
        return text[:max_chars]
    segs = _segments(text)
    hits = [len(pat.findall(s)) for s in segs]
    if not any(hits):
        return text[:max_chars]
    best_text, best_score = None, -1
    for i in range(len(segs)):
        window, size = [], 0
        for j in range(i, len(segs)):
            add = len(segs[j]) + (1 if window else 0)
            if size + add > max_chars:
                break
            window.append(segs[j])
            size += add
        if not window:
            continue
        score = sum(hits[i:i + len(window)])
        if score > best_score:
            best_score, best_text = score, " ".join(window)
    if best_text is None or best_score <= 0 or len(best_text) > max_chars:
        return text[:max_chars]
    return best_text


def evaluate(items, judge, evidence_for=None, retrieve_for=None):
    """retrieve_for: claim -> passages, timed and accounted separately:
    retrieval failures must not blur into NLI errors. Items whose evidence
    step failed or found nothing are recorded as errors (pred=None) - the
    chain broke before the judge, so no verdict is trustworthy (the
    never-default-to-neutral invariant)."""
    results = []
    for n, item in enumerate(items, 1):
        gold = CODE_TO_LABEL[item["entailment_label"]]
        retrieval_error = None
        t_ret = time.perf_counter()
        if retrieve_for is not None:
            try:
                passages = retrieve_for(item)
            except Exception as e:
                passages, retrieval_error = [], f"retrieval raised: {e!r}"
        else:
            passages = evidence_for(item)
        retrieval_s = time.perf_counter() - t_ret
        no_evidence = not passages
        t0 = time.perf_counter()
        if retrieval_error or no_evidence:
            verdict, error = {}, (retrieval_error
                                  or "no evidence passages retrieved")
        else:
            try:
                verdict = judge.judge(item["claim"], passages)
                error = verdict.get("error")
            except Exception as e:
                verdict, error = {}, f"judge raised: {e!r}"
        elapsed = time.perf_counter() - t0
        pred = None if (error or retrieval_error or no_evidence) \
            else verdict.get("label")
        rec = {
            "index": n,
            "claim": item["claim"][:300],
            "pair": (f'{item.get("claim_language")}->'
                     f'{item.get("reference_language")}'),
            "gold": gold, "gold_code": item["entailment_label"],
            "pred": pred, "pred_code": label_to_code(pred),
            "correct": pred == gold, "error": error,
            "elapsed_s": round(elapsed, 2),
            "retrieval_s": round(retrieval_s, 2),
        }
        if no_evidence:
            rec["no_evidence"] = True
        if not retrieval_error and no_evidence:
            rec["error"] = "no evidence passages retrieved"
        if verdict.get("usage"):
            rec["usage"] = verdict["usage"]
        results.append(rec)
        if n % 25 == 0 or n == len(items):
            ok = sum(1 for r in results if r["correct"])
            print(f"  {n}/{len(items)}: correct={ok}", flush=True)
    return results


def summarise(results):
    # Pure-Python metrics (AGENTS.md: no sklearn/SciPy). Error items count
    # as false negatives for their gold class, never as a predicted class.
    per_class, f1_raw = {}, {}
    for c in CLASSES:
        tp = sum(1 for r in results if r["gold"] == c and r["pred"] == c)
        fn = sum(1 for r in results if r["gold"] == c and r["pred"] != c)
        fp = sum(1 for r in results if r["gold"] != c and r["pred"] == c)
        p_ = tp / (tp + fp) if tp + fp else 0.0
        r_ = tp / (tp + fn) if tp + fn else 0.0
        f_ = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0.0
        f1_raw[c] = f_
        per_class[c] = {"precision": round(p_, 3), "recall": round(r_, 3),
                        "f1": round(f_, 3), "support": tp + fn}
    present = [c for c in CLASSES if per_class[c]["support"] > 0]
    # macro-F1 averages FULL-PRECISION per-class F1 (2026-10-10 fix: v1
    # averaged the 3-decimal display values, a small systematic bias; "m1").
    macro = (round(sum(f1_raw[c] for c in present) / len(present), 3)
             if present else 0.0)
    confusion = {g: {p: 0 for p in CLASSES + ["ERROR"]} for g in CLASSES}
    for r in results:
        confusion[r["gold"]][r["pred"] if r["pred"] in CLASSES else "ERROR"] += 1
    lat = sorted(r["elapsed_s"] for r in results if r["pred"])
    # Error items cost wall-clock time too - a 120 s endpoint timeout is the
    # worst case - and `lat` excludes them. Report both bases so a slow,
    # failure-heavy run cannot read as a fast one.
    lat_all = sorted(r["elapsed_s"] for r in results)
    ret = [r.get("retrieval_s") for r in results
           if r.get("retrieval_s") is not None]
    kinds = {}
    for r in results:
        if not r["pred"]:
            e = str(r.get("error") or "")
            if e == "unparseable_response":
                k = "unparseable_response"
            elif (e.startswith("retrieval raised")
                  or e == "no evidence passages retrieved"):
                k = "retrieval_error"
            elif ("Endpoint error" in e or "timed out" in e
                  or "Connection" in e or "Max retries" in e):
                k = "endpoint_error"
            else:
                k = "judge_error"
            kinds[k] = kinds.get(k, 0) + 1
    return {
        "n": len(results),
        "errors": sum(1 for r in results if not r["pred"]),
        "error_kinds": kinds,
        "accuracy": round(sum(1 for r in results if r["correct"])
                          / max(1, len(results)), 3),
        "macro_f1": macro,
        "per_class": per_class,
        "confusion": confusion,
        "mean_latency_s": round(sum(lat) / len(lat), 2) if lat else None,
        "median_latency_s": (round((lat[(len(lat) - 1) // 2]
                                    + lat[len(lat) // 2]) / 2, 2)
                             if lat else None),
        "mean_latency_s_all": (round(sum(lat_all) / len(lat_all), 2)
                               if lat_all else None),
        "median_latency_s_all": (round((lat_all[(len(lat_all) - 1) // 2]
                                        + lat_all[len(lat_all) // 2]) / 2, 2)
                                 if lat_all else None),
        "latency_basis": ("mean/median_latency_s exclude error items; the "
                          "_all keys cover every item, so a run whose errors "
                          "were slow (timeouts) stays visible"),
        "mean_retrieval_s": round(sum(ret) / len(ret), 3) if ret else None,
        "prompt_tokens_total": sum(
            r.get("usage", {}).get("prompt_tokens", 0) for r in results),
        "completion_tokens_total": sum(
            r.get("usage", {}).get("completion_tokens", 0) for r in results),
    }


def main():
    ap = argparse.ArgumentParser(description="Track 2A eval harness")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--out", default=None,
                    help="explicit result path (must not already exist)")
    ap.add_argument("--split", choices=["dev", "eval", "all"], default="dev")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=DEV_SEED)
    ap.add_argument("--sampler", choices=["prefix", "balanced"],
                    default="prefix",
                    help="how --limit cuts the split: dataset order (default, "
                         "reproduces the recorded dev runs) or class-stratified. "
                         "The first dataset rows are all entailment, so a "
                         "prefix slice is not a usable accuracy sample.")
    ap.add_argument("--backend", default=None,
                    choices=["lexical", "mlx", "ollama", "openai"])
    ap.add_argument("--evidence",
                    choices=["oracle", "retrieve", "retrieve-v2"],
                    default="oracle")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--prompt-config", default=None,
                    choices=sorted(PROMPT_CONFIGS),
                    help="judge prompt/judging config (default: PROMPT_CONFIG"
                         " env or 'baseline')")
    args = ap.parse_args()
    if args.out and Path(args.out).exists():
        sys.exit(f"output already exists: {args.out}")

    data_path = Path(args.data)
    if not data_path.exists():
        sys.exit(f"eval data not found: {data_path}\n"
                 "Run: python3 fetch_eval_data.py")
    rows = load_rows(data_path)
    idx = split_indices(len(rows), args.split, args.seed, DEV_SIZE)
    if args.sampler == "balanced":
        # Class-stratified draw of --limit items from the split (whole split
        # if no limit), re-ordered into file order by the sampler itself.
        # Selection happens before the overlap check so the provenance
        # describes the items actually evaluated, not the prefix they came
        # from. The dev split keeps its seed but not its exact 60 items.
        pool = [(i, rows[i]) for i in idx]
        picked = balanced_sample([rec for _, rec in pool],
                                 args.limit or len(pool), seed=args.seed)
        by_id = {id(rec): i for i, rec in pool}
        sel = sorted(by_id[id(rec)] for rec in picked)
    else:
        sel = list(idx[:args.limit] if args.limit else idx)
    items = [rows[i] for i in sel]
    if not items:
        sys.exit("no items selected")
    mix = Counter(CODE_TO_LABEL[r["entailment_label"]] for r in items)
    if len(mix) < len(CLASSES):
        print(f"WARNING: selected slice covers {len(mix)}/{len(CLASSES)} "
              f"class(es): {dict(mix)}. Macro-F1 then averages only the "
              "classes present, so the run is not comparable with a "
              "full-coverage one. The first dataset rows are all entailment: "
              "keep --limit at the full dev split (60, prefix order) or add "
              "--sampler balanced.")
    overlap = overlap_with_rest(rows, sel)

    backend = args.backend or LLM_BACKEND
    prompt_config = args.prompt_config or PROMPT_CONFIG
    pconf = get_prompt_config(prompt_config)  # unknown name: fail before any model traffic
    retrieve_for = None
    judge = None
    retrieval_desc = "oracle: gold reference_string (judgement step only)"
    if args.evidence == "retrieve":
        from ingest import build_corpus
        from retriever import build_retriever
        retriever = build_retriever(build_corpus())

        def retrieve_for(item):
            return retriever.retrieve(item["claim"], top_k=args.top_k)
        retrieval_desc = "legacy 526-passage CLI corpus (plumbing only)"
    elif args.evidence == "retrieve-v2":
        # Reuse main.Pipeline verbatim: booklet PDF corpus + claim-language
        # adapter heuristic, i.e. the stack production runs. The flag beats
        # the RETRIEVAL_CONFIG env default on purpose. booklet_url and
        # reference_string are never consulted at prediction time.
        import logging
        import main as main_mod
        main_mod.RETRIEVAL_CONFIG = "v2"
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        pipe = main_mod.Pipeline(logging.getLogger("eval-retrieve-v2"),
                                 backend=backend, prompt_config=prompt_config)
        judge = pipe.judge

        def retrieve_for(item):
            return pipe._retrieve_booklet(item["claim"], args.top_k)
        retrieval_desc = ("60-booklet PDF corpus, global dense, "
                          "claim-lang adapter (production stack)")

    print(f"Eval: {len(items)} items | backend={backend} | "
          f"evidence={args.evidence} ({retrieval_desc}) | "
          f"split={args.split} ({args.sampler}) | seed={args.seed} | "
          f"mix={dict(mix)} | "
          f"prompt={prompt_config} (T={pconf['temperature']}, "
          f"evidence_style={pconf['evidence']}, window={pconf['window']})")

    if judge is None:
        judge = build_judge(backend, prompt_config)
    t0 = time.perf_counter()
    if args.evidence == "oracle":
        results = evaluate(
            items, judge,
            evidence_for=lambda it: oracle_evidence(it, pconf))
    else:
        results = evaluate(items, judge, retrieve_for=retrieve_for)
    summary = summarise(results)

    payload = {
        "meta": {
            "created_utc": datetime.now(timezone.utc)
                               .isoformat(timespec="seconds"),
            "backend": backend,
            "model": (MLX_MODEL if backend == "mlx" else
                      JUDGE_MODEL if backend == "openai" else
                      OLLAMA_MODEL if backend == "ollama" else None),
            "endpoint": OPENAI_BASE_URL if backend == "openai" else None,
            "retrieval": retrieval_desc,
            "data_file": str(data_path), "n_items": len(items),
            "split": args.split, "seed": args.seed,
            "sampler": args.sampler,
            "evidence_mode": args.evidence,
            "prompt_config": prompt_config,
            "temperature": pconf["temperature"],
            "max_tokens": pconf["max_tokens"],
            "evidence_style": pconf["evidence"],
            "evidence_window": pconf["window"],
            "label_parse_version": LABEL_PARSE_VERSION,
            "metrics_version": "m3-error-verdicts-unscored",
            "dataset_sha256": hashlib.sha256(
                data_path.read_bytes()).hexdigest(),
            "class_mix": dict(mix),
            "overlap_with_rest": overlap,
            "note": ("oracle mode measures the judgement step with gold "
                     "evidence, not retrieval quality"
                     if args.evidence == "oracle" else
                     "end-to-end via main.Pipeline stack: evidence from "
                     "retrieval; retrieval misses and unparseable replies "
                     "are recorded as errors (pred=None), never labelled"),
            "elapsed_total_s": round(time.perf_counter() - t0, 1),
        },
        "summary": summary,
        "items": results,
    }
    tag = f"_{args.split}_{backend}_{args.evidence}"
    if prompt_config != "baseline":
        tag += f"_{prompt_config}"  # ablation runs must not clobber baseline files
    if args.sampler != "prefix":
        # A stratified slice shares no items with a prefix slice of the same
        # size: keep it out of the same filename stem, or a smoke run gets
        # compared against the recorded dev numbers it cannot be compared to.
        tag += f"_{args.sampler}"
    out = (Path(args.out) if args.out else DATA_DIR /
           f"eval_results_{datetime.now():%Y%m%d_%H%M%S_%f}{tag}.json")
    with out.open("x", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"\naccuracy  {summary['accuracy']}  "
          f"(errors: {summary['errors']}/{summary['n']})")
    print(f"macro_f1  {summary['macro_f1']}")
    for c, m in summary["per_class"].items():
        print(f"  {c:<14} P={m['precision']:<6} R={m['recall']:<6} "
              f"F1={m['f1']:<6} n={m['support']}")
    print(f"dev/held-out overlap: cluster {overlap['cluster_overlap']}/"
          f"{overlap['n_selected']} selected | exact triples "
          f"{overlap['exact_triple_overlap']} (details in meta)")
    print(f"results JSON: {out}")


if __name__ == "__main__":
    main()
