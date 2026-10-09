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
  lexical   BM25 over whitespace tokens - lower-cost baseline.

Metrics: Recall@1/3/5 (any gold passage in top-K), document routing (gold
document hit by top-1), failure breakdown (wrong booklet vs wrong passage),
per-claim-language and same-vs-cross-language Recall@5.

Usage:
  python3 fetch_booklets.py                  # first build data/booklets/
  python3 eval_e2e.py --limit 60             # smoke, class-balanced sample
  python3 eval_e2e.py                         # full 1488-item eval
"""
import argparse
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from config import BOOKLET_CORPUS_JSON, DATA_DIR
from fetch_booklets import DATASET_PATH, booklet_key, load_dataset
from sampling import balanced_sample, label_counts

TOPK = (1, 3, 5)


# ---------------------------------------------------------------- gold labelling

def norm_text(s: str) -> str:
    """Aggressive normalisation: NFKC, lowercase, alnum-only, spaces squashed.

    Used for BOTH sides of the evidence<->passage matcher so PDF layout noise
    (ligatures, doubled spaces, hyphenation artefacts) cannot break matching.
    """
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


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

class BM25:
    """Minimal BM25 (k1=1.2, b=0.75) over whitespace tokens of normalised text."""

    def __init__(self, texts, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.doc_tok = [t.split() for t in texts]
        self.doc_len = [len(t) for t in self.doc_tok]
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) or 1.0
        df = Counter()
        tf = []
        for toks in self.doc_tok:
            c = Counter(toks)
            tf.append(c)
            df.update(c.keys())
        self.tf = tf
        n = len(texts)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5))
                    for t, d in df.items()}
        self.index = defaultdict(list)
        for i, toks in enumerate(self.doc_tok):
            for t in set(toks):
                self.index[t].append(i)

    def top_k(self, query: str, k: int):
        scores = {}
        for t in norm_text(query).split():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.index.get(t, ()):
                f = self.tf[i][t]
                denom = f + self.k1 * (1 - self.b + self.b
                                       * self.doc_len[i] / self.avg_len)
                scores[i] = scores.get(i, 0.0) + idf * f * (self.k1 + 1) / denom
        top = sorted(scores.items(), key=lambda x: -x[1])[:k]
        return top


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


def ollama_status():
    """Quick reachability probe for a local Ollama server."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags", method="GET")
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
    for i, r in enumerate(records):
        key = f"{r['claim_language']}->{r['reference_language']}::{r['claim']}"
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
    ap.add_argument("--configs", default="emb_v1,emb_v2,lexical")
    ap.add_argument("--translate", action="store_true",
                    help="translate cross-lingual claims via Ollama before "
                         "encoding (emb_v2 only)")
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

    need_emb = {"emb_v1", "emb_v2"} & set(args.configs.split(","))
    retriever, corpus_mat = None, None
    if need_emb:
        from retriever import Retriever
        retriever = Retriever()
        retriever.build_index(corpus)
        corpus_mat = retriever.corpus_embeddings
        corpus_mat = (corpus_mat / (np.linalg.norm(corpus_mat, axis=1,
                                                   keepdims=True) + 1e-9))

    bm25 = BM25([r["text"] for r in corpus]) \
        if "lexical" in args.configs else None

    results = {}
    for cfg in [c.strip() for c in args.configs.split(",") if c.strip()]:
        t0 = time.time()
        if cfg == "lexical":
            ranks = [bm25.top_k(r["claim"], max(TOPK)) for r in records]
            note = "BM25 on normalised tokens, no translation"
        else:
            queries, note = translate_queries(records, cfg, args.translate)
            if cfg == "emb_v1":
                adapters = ["de_CH"] * len(records)
            else:
                adapters = [ADAPTER.get(r["reference_language"], "de_CH")
                            for r in records]
            ranks = embed_rank(retriever, queries, adapters, corpus_mat,
                               max(TOPK))
        res = eval_config(cfg, records, gold_map, ranks, corpus)
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
        "evidence_matching": cov,
        "scope": "full corpus, no booklet/language filter (end-to-end)",
        "integrity": {
            "reference_string_used_for": "gold-passage labelling only",
            "query_side": "claim (+translation); never the reference",
            "booklet_url_used_for": "gold labelling only, never a filter",
        },
        "configs": results,
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
