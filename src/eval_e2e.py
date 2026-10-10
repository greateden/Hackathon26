"""
End-to-end evidence-based retrieval evaluation (Track 2A Priority 1+2).

Gold relevance is derived by matching each item's oracle `reference_string`
against passages extracted from the ORIGINAL booklet PDFs
(data/booklets/corpus.json, built by fetch_booklets.py). This separates:

  extraction coverage  can the reference be found in the extracted text at
                       all - the ceiling for ANY retriever (reported as
                       `gold_found`, never mixed into retrieval maths).
  retrieval quality    given that ceiling, does top-K retrieval recover the
                       gold passage(s) from the whole 60-booklet corpus?

Integrity rules enforced here:
  * `reference_string` (oracle evidence) is used ONLY to LABEL gold passages
    in the corpus built from original PDFs. It is never indexed, never part
    of any query, never shown to the judge.
  * `booklet_url` is used ONLY for gold labelling (which PDF the evidence
    came from). Retrieval queries the FULL corpus with no booklet/language
    filter - the system must find the right booklet on its own.
  * Query side = the claim (+ optional translation). Never the reference.

Configurations compared in one pass:
  emb_v1    as previously measured: claim encoded untranslated with the
            de_CH adapter (cross-lingual pairs suffer).
  emb_v2    claim encoded with the EVIDENCE-language adapter; with
            --translate, claims are first translated into the evidence
            language via Ollama Apertus (cached; falls back to untranslated
            and says so in the report).
  lexical   legacy ASYMMETRIC BM25 (protocol lex-asym-v1): docs indexed as
            raw whitespace tokens, query normalised. Known tokenisation
            mismatch, kept ONLY so the historical §5.4 ranking stays
            reproducible; do not present as the deployable lexical design.
  lexical_v2
            deployable SYMMETRIC BM25 (protocol lex-sym-v2): norm_text on
            BOTH document and query tokens.
  hyb_rrf   hybrid: RRF over global BM25 + global dense candidates
            (query side identical to emb_v2).
  two_stage / two_stage_lex
            two-stage retrieval: rank booklets (claim-side BM25 on
            whole-booklet text + mean-of-top-3 dense score, RRF-fused),
            then gather + RRF-fuse lexical/dense passage candidates from
            the top --doc-top-n booklets only. two_stage_lex is the
            all-lexical variant (no embedding model needed).
            See hybrid_retrieval.py; no gold booklet info at query time.

Adapter policy (--adapter-policy, default "claim" = deployable):
  claim     dense query adapter chosen from the CLAIM's own language via
            the same heuristic the CLI uses - no gold field at query time.
  oracle    adapter chosen from each item's gold reference_language.
            DIAGNOSTIC ONLY: that information does not exist at prediction
            time, so oracle runs measure a ceiling, never a deployable
            system. This is what the pre-2026-10-10 (§5.4) emb_v2/hybrid
            runs did; the default change is protocol v2.

Metrics: Recall@1/3/5 (any gold passage in top-K), document routing (gold
document hit by top-1), failure breakdown (wrong booklet vs wrong passage),
per-claim-language and same-vs-cross-language Recall@5.

Usage:
  python3 fetch_booklets.py                  # first build data/booklets/
  python3 eval_e2e.py --limit 60             # smoke, class-balanced sample
  python3 eval_e2e.py                         # full 1488-item eval
  python3 eval_e2e.py --limit 60 --configs lexical,lexical_v2  # BM25 A/B
  python3 eval_e2e.py --limit 60 --adapter-policy oracle        # DIAGNOSTIC
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from config import BOOKLET_CORPUS_JSON, DATA_DIR
from fetch_booklets import DATASET_PATH, booklet_key, load_dataset
from hybrid_retrieval import (BM25, TwoStageRetriever,
                              detect_query_language, index_cache_key,
                              load_index, norm_text, save_index)
from sampling import balanced_sample, label_counts

TOPK = (1, 3, 5)

ALL_CONFIGS = ("lexical", "lexical_v2", "emb_v1", "emb_v2", "hyb_rrf",
               "two_stage", "two_stage_lex")


# ---------------------------------------------------------------- gold labelling


def ref_probes(ref_norm: str):
    """A few contiguous normalised probes sampled from the evidence."""
    n = len(ref_norm)
    if n < 40:
        return [ref_norm]
    probes = [ref_norm[:60]]
    mid = n // 2
    probes.append(ref_norm[mid:mid + 60])
    probes.append(ref_norm[-60:])
    return probes


def find_gold(rec: dict, doc_passages: dict, min_coverage: float = 0.5):
    """Locate the corpus passages that contain this item's oracle evidence.

    Stage 1 (probe): the evidence's 60-char normalised probes appear verbatim
    inside a passage -> that passage is gold. Stage 2 (fallback): count how
    many 40-char shingles of the evidence appear in each passage of the
    source booklet; passages covering >= 30% of the evidence's shingles are
    gold, but only if the BEST passage covers >= min_coverage overall.

    Returns (gold_indices, method) with method in
    {"probe", "shingle", "not_found", "wrong_doc"}.
    """
    doc_id = booklet_key(rec["booklet_url"])
    entries = doc_passages.get(doc_id)
    if not entries:
        return [], "wrong_doc"          # booklet missing from the index

    ref_norm = norm_text(rec["reference_string"])
    probes = [p for p in ref_probes(ref_norm) if len(p) >= 30]

    hits = set()
    for probe in probes:
        for i, ntext in entries:
            if probe in ntext:
                hits.add(i)
    if hits:
        return sorted(hits), "probe"

    # Shingle fallback: evidence may be split/reordered by PDF layout.
    shingles = [ref_norm[k:k + 40] for k in range(0, len(ref_norm) - 39, 40)]
    shingles = [s for s in shingles if len(s) >= 30]
    if not shingles:
        return [], "not_found"
    best_i, best_c = None, 0.0
    counts = {}
    for i, ntext in entries:
        c = sum(1 for s in shingles if s in ntext)
        if c:
            counts[i] = c
        if c > best_c:
            best_i, best_c = i, c
    if best_i is None or best_c / len(shingles) < min_coverage:
        return [], "not_found"
    gold = [i for i, c in counts.items() if c / len(shingles) >= 0.3]
    return sorted(gold), "shingle"


# ------------------------------------------------------------------- retrieval
# (BM25 + RRF + two-stage machinery live in hybrid_retrieval.py so the CLI
#  and the eval share one implementation.)


def embed_rank(retriever, query_texts, adapters, corpus_mat, topk):
    """Batch-encode queries (grouped by adapter) and return per-item rankings."""
    ranks = [None] * len(query_texts)
    by_adapter = defaultdict(list)
    for i, (q, a) in enumerate(zip(query_texts, adapters)):
        by_adapter[a].append(i)
    for adapter, idxs in by_adapter.items():
        texts = [query_texts[i] for i in idxs]
        embs = retriever.encode(texts, lang_code=adapter)
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
        sims = embs @ corpus_mat.T          # (batch, corpus)
        for row, i in enumerate(idxs):
            sims_row = sims[row]
            top = np.argsort(-sims_row)[:topk]
            ranks[i] = [(int(j), float(sims_row[j])) for j in top]
    return ranks


def batched_sims(retriever, query_texts, adapters, corpus_mat):
    """Per-item cosine similarity rows (whole corpus) - batch-encoded so the
    hybrid configs and emb_v1/v2 see identical dense scores."""
    sims = [None] * len(query_texts)
    by_adapter = defaultdict(list)
    for i, (q, a) in enumerate(zip(query_texts, adapters)):
        by_adapter[a].append(i)
    for adapter, idxs in by_adapter.items():
        texts = [query_texts[i] for i in idxs]
        embs = retriever.encode(texts, lang_code=adapter)
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
        rows = embs @ corpus_mat.T
        for row, i in enumerate(idxs):
            sims[i] = rows[row]
    return sims


def failure_examples(records, gold_map, ranks, corpus, n_ex):
    """Keep top-ranked passages for MISSING items (gold exists, top-5 has
    none). Some misses may still be defensible evidence - this is for manual
    inspection, not automated scoring."""
    out = []
    for n, rec in enumerate(records):
        gm = gold_map[n]
        if not gm["gold"]:
            continue
        top = [i for i, _ in ranks[n]]
        if gm["gold"] & set(top[:max(TOPK)]):
            continue
        out.append({
            "index": n,
            "claim": rec["claim"],
            "claim_lang": rec["claim_language"],
            "ref_lang": rec["reference_language"],
            "gold_doc": gm["doc_id"],
            "gold_passages": sorted(gm["gold"]),
            "top5": [{"doc_id": corpus[i]["doc_id"],
                      "lang": corpus[i]["lang"],
                      "is_gold": i in gm["gold"],
                      "text_head": corpus[i]["text"][:160]}
                     for i in top[:max(TOPK)]],
        })
        if len(out) >= n_ex:
            break
    return out


# ------------------------------------------------------------------- metrics

def run_evidence_matching(records, corpus):
    """Label gold passages for every eval item. Returns (gold_map, stats)."""
    doc_passages = defaultdict(list)
    for i, rec in enumerate(corpus):
        doc_passages[rec["doc_id"]].append((i, norm_text(rec["text"])))

    gold_map, methods, failures = {}, Counter(), []
    for n, rec in enumerate(records):
        gold, method = find_gold(rec, doc_passages)
        methods[method] += 1
        gold_map[n] = {"gold": set(gold), "method": method,
                       "doc_id": booklet_key(rec["booklet_url"])}
        if method in ("not_found", "wrong_doc") and len(failures) < 20:
            failures.append({"index": n, "claim": rec["claim"][:80],
                             "ref_lang": rec["reference_language"],
                             "method": method,
                             "doc_id": booklet_key(rec["booklet_url"])})
    found = methods["probe"] + methods["shingle"]
    stats = {"methods": dict(methods),
             "coverage": found / len(records) if records else 0.0}
    return gold_map, stats, failures


def eval_config(name, records, gold_map, ranks, corpus):
    """Recall@K + document routing + failure classes for one ranked run."""
    hits = Counter()
    scored = 0
    mrr_sum = 0.0
    doc_route1 = 0
    failure_classes = Counter()
    per_lang = defaultdict(lambda: [0, 0])        # lang -> [hits@5, n]
    pair_split = defaultdict(lambda: [0, 0])      # same|cross -> [hits@5, n]

    for n, rec in enumerate(records):
        gm = gold_map[n]
        if not gm["gold"]:
            continue
        scored += 1
        top = [i for i, _ in ranks[n]]
        gold = gm["gold"]
        for k in TOPK:
            if gold & set(top[:k]):
                hits[k] += 1
        for rank_pos, i in enumerate(top[:5], 1):
            if i in gold:
                mrr_sum += 1.0 / rank_pos
                break
        if top and corpus[top[0]]["doc_id"] == gm["doc_id"]:
            doc_route1 += 1
        if not (gold & set(top)):
            top_doc = corpus[top[0]]["doc_id"] if top else None
            key = "no_results" if not top else (
                "wrong_booklet" if top_doc != gm["doc_id"] else "wrong_passage")
            failure_classes[key] += 1
        bucket = bool(gold & set(top[:5]))
        per_lang[rec["claim_language"]][0] += bucket
        per_lang[rec["claim_language"]][1] += 1
        pair = "same" if rec["claim_language"] == rec["reference_language"] \
            else "cross"
        pair_split[pair][0] += bucket
        pair_split[pair][1] += 1

    def rate(x, y):
        return round(x / y, 4) if y else None

    return {
        "n_scored": scored,
        "recall": {f"r@{k}": rate(hits[k], scored) for k in TOPK},
        "mrr@5": rate(mrr_sum, scored),
        "doc_routing_top1": rate(doc_route1, scored),
        "failure_classes": dict(failure_classes),
        "per_claim_lang_r@5": {k: {"r@5": rate(v[0], v[1]), "n": v[1],
                                   "hits@5": v[0]}
                               for k, v in sorted(per_lang.items())},
        "same_vs_cross_r@5": {k: {"r@5": rate(v[0], v[1]), "n": v[1],
                                  "hits@5": v[0]}
                              for k, v in sorted(pair_split.items())},
    }


# --------------------------------------------------------------- translation

ADAPTER = {"de": "de_CH", "fr": "fr_CH", "it": "it_CH"}


def adapters_for(records, policy):
    """Dense-query adapter choice per item (see module docstring).

    'oracle' reads the gold reference_language: DIAGNOSTIC ONLY. It
    measures the ceiling IF the evidence language were known at query time
    and is what the pre-2026-10-10 §5.4 runs did; it must never be
    described as a deployable configuration. 'claim' (default) detects the
    language from the claim text with the CLI's heuristic - no gold field
    is consulted at prediction time."""
    if policy == "oracle":
        return [ADAPTER.get(r["reference_language"], "de_CH")
                for r in records]
    return [ADAPTER.get(detect_query_language(r["claim"]), "de_CH")
            for r in records]


def ollama_status():
    """Quick reachability probe for the CONFIGURED Ollama endpoint.

    2026-10-10 fix: this used to hardcode localhost:11434, so a container
    or a custom OLLAMA_BASE_URL was reported as 'not reachable' while
    actually being up (and vice versa)."""
    import urllib.request
    from config import OLLAMA_BASE_URL
    url = OLLAMA_BASE_URL.rstrip("/")
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name", "") for m in data.get("models", [])]
        return True, models
    except Exception:
        return False, []


def translate_queries(records, config, translate_flag):
    """Return (query_texts, mode_note) for an embedding config.

    v2 intends claim->evidence-language translation (SwissBERT cross-lingual
    similarity is weak without it). Translation runs via local Ollama Apertus
    when reachable; otherwise queries stay untranslated and the report says
    so - silently skipping translation would fake a different system config.
    """
    if config == "emb_v1":
        return [r["claim"] for r in records], "none (v1: de_CH adapter)"

    ok, _ = ollama_status()
    if not translate_flag:
        return [r["claim"] for r in records], \
            "untranslated (evidence-language adapter only; --translate off)"
    if not ok:
        return [r["claim"] for r in records], \
            "untranslated (Ollama not reachable; evidence-language adapter only)"

    from config import OLLAMA_MODEL, OLLAMA_BASE_URL
    cache_path = DATA_DIR / "eval" / "translation_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) \
        if cache_path.exists() else {}
    out, missing = [None] * len(records), []
    # Cache keys carry the model id + prompt version ("t2"): a translation
    # made by a different model or prompt is a DIFFERENT experiment input
    # and must not silently reuse v1 cache entries.
    for i, r in enumerate(records):
        key = (f"t2::{OLLAMA_MODEL}::"
               f"{r['claim_language']}->{r['reference_language']}"
               f"::{r['claim']}")
        if r["claim_language"] == r["reference_language"]:
            out[i] = r["claim"]
        elif key in cache:
            out[i] = cache[key]
        else:
            missing.append((i, key, r))
    if missing:
        print(f"  translating {len(missing)} claims via Ollama "
              f"{OLLAMA_MODEL} ...")
        texts = [r["claim"] for _, _, r in missing]
        pairs = [(r["claim_language"], r["reference_language"])
                 for _, _, r in missing]
        done, note = ollama_translate_batch(texts, pairs, OLLAMA_MODEL,
                                            OLLAMA_BASE_URL)
        if done is None:
            return [r["claim"] for r in records], note
        for (i, key, _), tr in zip(missing, done):
            out[i] = tr
            cache[key] = tr
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False),
                              encoding="utf-8")
    return out, "translated via Ollama Apertus (cache-backed)"


def ollama_translate_batch(texts, pairs, model, base_url, timeout=60):
    """Translate claims via local Ollama /api/chat (temperature 0, stdlib only).

    Returns (translations, note). On ANY failure returns (None, note) so the
    caller falls back to untranslated queries and the report states the truth.
    """
    import urllib.request
    out = []
    for text, (src, tgt) in zip(texts, pairs):
        if src == tgt:
            out.append(text)
            continue
        prompt = ("Translate the following Swiss political claim from "
                  f"{src.upper()} to {tgt.upper()}. Output ONLY the "
                  f"translation, no explanation.\n\n{text}")
        body = json.dumps({
            "model": model, "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.0},
        }).encode()
        try:
            req = urllib.request.Request(
                f"{base_url}/api/chat", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                reply = json.loads(resp.read().decode()) \
                    .get("message", {}).get("content", "").strip()
            out.append(reply if reply else text)
        except Exception as e:
            return None, f"untranslated (translation failed at {type(e).__name__})"
    return out, "translated via Ollama Apertus"


# -------------------------------------------------------------------- runner

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Evidence-based retrieval eval over booklet PDF corpus")
    ap.add_argument("--limit", type=int, default=0,
                    help="class-balanced sample size (0 = all items)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--configs", default="emb_v1,emb_v2,lexical",
                    help=f"comma list from {list(ALL_CONFIGS)}")
    ap.add_argument("--translate", action="store_true",
                    help="translate cross-lingual claims via Ollama before "
                         "encoding (emb_v2 + hybrid configs)")
    ap.add_argument("--doc-top-n", type=int, default=3,
                    help="two-stage: booklets routed into stage 2")
    ap.add_argument("--cand", type=int, default=8,
                    help="candidate passages per source list "
                         "(stage 2 / global fusion pool)")
    ap.add_argument("--per-doc-cap", type=int, default=0,
                    help="max passages kept per booklet (0 = no cap)")
    ap.add_argument("--dump-failures", type=int, default=0,
                    help="include up to N top-5 misses per config")
    ap.add_argument("--adapter-policy", choices=["claim", "oracle"],
                    default="claim",
                    help="dense-query adapter choice: 'claim' (default, "
                         "deployable) = adapter from claim-language "
                         "detection; 'oracle' = gold reference_language, "
                         "DIAGNOSTIC ONLY")
    ap.add_argument("--lex-protocol", choices=["asym", "sym"],
                    default="asym",
                    help="tokenisation contract for the lexical channel of "
                         "every stack that uses one (lexical_v2 is always "
                         "symmetric; hybrid and two-stage stacks follow this "
                         "flag). 'asym' (default) = the historically "
                         "reported lex-asym-v1 behaviour, kept only so §5.4 "
                         "stays reproducible; 'sym' = lex-sym-v2, the "
                         "corrected channel to compare against dense")
    ap.add_argument("--out", default=None, help="result JSON path")
    args = ap.parse_args(argv)

    if not BOOKLET_CORPUS_JSON.exists():
        sys.exit(f"corpus not found: {BOOKLET_CORPUS_JSON}\n"
                 "build it first:  python3 fetch_booklets.py")

    all_records = load_dataset()
    records = (balanced_sample(all_records, args.limit, seed=args.seed)
               if args.limit else all_records)
    corpus = json.loads(BOOKLET_CORPUS_JSON.read_text(encoding="utf-8"))
    docs = sorted({r["doc_id"] for r in corpus})
    print(f"Eval items: {len(records)} | corpus: {len(corpus)} passages "
          f"from {len(docs)} booklets")
    print(f"Class mix: {label_counts(records)}")

    t0 = time.time()
    gold_map, cov, fails = run_evidence_matching(records, corpus)
    print(f"Evidence located in extracted PDF text: "
          f"{cov['coverage']:.3f} of {len(records)} "
          f"({time.time() - t0:.1f}s) {cov['methods']}")
    if fails:
        print("Sample items whose evidence could NOT be located "
              "(extraction layer):")
        for f in fails[:5]:
            print(f"  [{f['method']} {f['ref_lang']}] {f['claim'][:70]}")

    cfg_list = [c.strip() for c in args.configs.split(",") if c.strip()]
    unknown = set(cfg_list) - set(ALL_CONFIGS)
    if unknown:
        sys.exit(f"unknown configs: {sorted(unknown)}; "
                 f"choose from {list(ALL_CONFIGS)}")

    need_dense = bool({"emb_v1", "emb_v2", "hyb_rrf", "two_stage"}
                      & set(cfg_list))
    retriever, corpus_mat = None, None
    cache_note = "n/a (no embedding configs)"
    if need_dense:
        from retriever import Retriever
        key = index_cache_key(corpus)
        corpus_mat = load_index(key, n_expected=len(corpus))
        cache_note = (f"loaded data/cache/emb_{key}.npy (cached, not rebuilt)"
                      if corpus_mat is not None else
                      f"built now, cached as data/cache/emb_{key}.npy")
        retriever = Retriever()
        if corpus_mat is None:
            retriever.build_index(corpus)
            corpus_mat = retriever.corpus_embeddings
            save_index(key, corpus_mat)
        corpus_mat = (corpus_mat / (np.linalg.norm(corpus_mat, axis=1,
                                                   keepdims=True) + 1e-9))
    print(f"Embedding index: {cache_note}")

    lex_texts = [r["text"] for r in corpus]
    bm25 = BM25(lex_texts) if "lexical" in cfg_list else None
    bm25v2 = BM25(lex_texts, norm_docs=True) \
        if "lexical_v2" in cfg_list else None
    if args.adapter_policy == "oracle":
        print("NOTE: --adapter-policy oracle reads the gold reference "
              "language at query time: DIAGNOSTIC ONLY, not a deployable "
              "configuration.")

    results = {}
    for cfg in cfg_list:
        t0 = time.time()
        use_translate = args.translate and args.adapter_policy == "oracle"
        if cfg == "lexical":
            ranks = [bm25.top_k(r["claim"], max(TOPK)) for r in records]
            note = ("legacy asymmetric BM25: raw doc tokens vs normalised "
                    "query (lex-asym-v1)")
        elif cfg == "lexical_v2":
            ranks = [bm25v2.top_k(r["claim"], max(TOPK)) for r in records]
            note = "symmetric BM25: norm_text on docs AND query (lex-sym-v2)"
        elif cfg in ("emb_v1", "emb_v2"):
            queries, note = translate_queries(records, cfg, use_translate)
            if cfg == "emb_v1":
                adapters = ["de_CH"] * len(records)
            else:
                adapters = adapters_for(records, args.adapter_policy)
                note += f"; adapter-policy={args.adapter_policy}"
            ranks = embed_rank(retriever, queries, adapters, corpus_mat,
                               max(TOPK))
        else:
            # Hybrid configs: query side identical to emb_v2 under the SAME
            # adapter policy (oracle reproduces the historical
            # evidence-language setup for comparability; claim is the
            # deployable default). Booklet routing is computed from the
            # claim at query time - no gold booklet info is consulted.
            ts_kw = dict(doc_top_n=args.doc_top_n,
                         cand_per_source=args.cand,
                         per_doc_cap=args.per_doc_cap,
                         lex_protocol=args.lex_protocol)
            if cfg == "hyb_rrf":
                ts = TwoStageRetriever(corpus, corpus_mat=corpus_mat,
                                       mode="global", **ts_kw)
            elif cfg == "two_stage":
                ts = TwoStageRetriever(corpus, corpus_mat=corpus_mat,
                                       mode="two_stage", **ts_kw)
            else:  # two_stage_lex: routing + stage 2 purely lexical, no model
                ts = TwoStageRetriever(corpus, mode="two_stage",
                                       use_dense=False, **ts_kw)
            queries, note = translate_queries(records, "emb_v2",
                                              use_translate)
            adapters = adapters_for(records, args.adapter_policy)
            note += f"; adapter-policy={args.adapter_policy}"
            sims_rows = ([None] * len(records)
                         if cfg == "two_stage_lex" or corpus_mat is None
                         else batched_sims(retriever, queries, adapters,
                                           corpus_mat))
            t_rank = time.time()
            ranks = [ts.retrieve(r["claim"], max(TOPK),
                                 sims=sims_rows[i])
                     for i, r in enumerate(records)]
            note += (f"; {cfg} docs={args.doc_top_n} "
                     f"cand={args.cand} cap={args.per_doc_cap} rrf_k=60 "
                     f"lex={args.lex_protocol}")
        res = eval_config(cfg, records, gold_map, ranks, corpus)
        if args.dump_failures:
            res["failure_examples"] = failure_examples(
                records, gold_map, ranks, corpus, args.dump_failures)
        res["query_mode"] = note
        res["seconds"] = round(time.time() - t0, 1)
        results[cfg] = res
        r = res["recall"]
        print(f"\n[{cfg}]  n={res['n_scored']}  ({res['seconds']}s)  {note}")
        print(f"  R@1={r['r@1']}  R@3={r['r@3']}  R@5={r['r@5']}  "
              f"MRR@5={res['mrr@5']}  doc-route@1={res['doc_routing_top1']}")
        print(f"  failures: {res['failure_classes']}")
        for k, v in res["same_vs_cross_r@5"].items():
            print(f"  {k}-language: R@5={v['r@5']} (n={v['n']})")

    out_path = Path(args.out) if args.out else \
        DATA_DIR / ("eval_results_"
                   f"{time.strftime('%Y%m%d_%H%M%S')}_retrieval.json")
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task": "evidence-based retrieval (claim -> passages from booklets)",
        "n_items": len(records),
        "sampling": {"mode": "class-balanced" if args.limit else "full",
                     "seed": args.seed,
                     "class_counts": label_counts(records)},
        "corpus": {"passages": len(corpus), "booklets": len(docs),
                   "built_from": "original booklet PDFs only"},
        "embedding_index": cache_note,
        "adapter_policy": args.adapter_policy,
        "protocol_versions": {
            "lexical": "lex-asym-v1 (legacy: raw doc tokens, query "
                       "normalised - kept for §5.4 comparability only)",
            "lexical_v2": "lex-sym-v2 (norm_text on both sides)",
            "hybrid_lexical": (
                "lex-sym-v2 (norm_text on both sides)"
                if args.lex_protocol == "sym"
                else "lex-asym-v1 in every hybrid/two-stage lexical leg "
                     "(--lex-protocol asym: the §5.4 defect, kept for "
                     "reproducibility; not a fair lexical baseline)"),
            "adapters": f"policy={args.adapter_policy}"
                        + (" | oracle uses the gold reference_language at "
                           "query time: diagnostic ceiling, NOT deployable"
                           if args.adapter_policy == "oracle" else ""),
        },
        "hybrid_params": {"doc_top_n": args.doc_top_n, "cand": args.cand,
                          "per_doc_cap": args.per_doc_cap, "rrf_k": 60},
        "evidence_matching": cov,
        "scope": "full corpus, no booklet/language filter (end-to-end)",
        "integrity": {
            "reference_string_used_for": "gold-passage labelling only",
            "query_side": "claim (+translation); never the reference",
            "booklet_url_used_for": "gold labelling only, never a filter",
            "adapter_policy_uses_gold_language":
                args.adapter_policy == "oracle",
        },
        "configs": results,
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
