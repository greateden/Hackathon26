"""
Retrieval-quality evaluation (no LLM needed).

We have no gold claim->evidence labels, but the upstream repos ship a
human-annotated *parallel* corpus: each row holds a German passage and its
official FR/IT/RM counterpart from the same booklet. We use the German
segment as a probe query and check whether the retriever returns the
aligned foreign-language segment. This is a proxy for "can retrieval find
the evidence for a claim?", using ground truth we actually have.

Metrics: Recall@1 / Recall@5 over the foreign-language corpus.
Chance level for R@1 is 1/N, printed alongside for reference.

Two switches for diagnosis:
  --adapter        set the SwissBERT language adapter per side (as upstream
                   align_with_ssb.py does) instead of encoding everything
                   with the default adapter
  --same-lang      control run: query and corpus in the same language
                   (sanity check that the encoder does semantic matching)

Usage:
    python3 eval_retrieval.py                      # cross-lingual, default
    python3 eval_retrieval.py --adapter
    python3 eval_retrieval.py --same-lang
"""
"""
Retrieval-quality evaluation (no LLM needed).

We have no gold claim->evidence labels, but the upstream repos ship a
human-annotated *parallel* corpus: each row holds a German passage and its
official FR/IT/RM counterpart from the same booklet. We use the German
segment as a probe query and check whether the retriever returns the aligned
foreign-language segment out of the whole foreign-language corpus.

This is a proxy for "can retrieval find the evidence for a claim?" using
ground truth we actually have. It answers the question the hackathon cares
about: is cross-lingual retrieval reliable enough to feed the judge?

Metric: Recall@1 / Recall@5, with the 1/N chance level printed for reference.

Two settings, because production currently encodes queries with the de_CH
adapter but encodes passages with each passage's own language adapter:
  --mode mismatched   query=de_CH, corpus=per-language adapter  (as shipped)
  --mode uniform      query=de_CH, corpus=de_CH for every language
  --mode same-lang    DE->DE control (self-match excluded) to confirm the
                      encoder is not degenerate

Usage:
    python3 eval_retrieval.py
    python3 eval_retrieval.py --mode uniform
    python3 eval_retrieval.py --mode same-lang
"""
import sys
import os
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from retriever import Retriever

GOLD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "repos", "VotingBooklets",
                        "gold_files", "gold_alignment")

ADAPTER = {"de": "de_CH", "fr": "fr_CH", "it": "it_CH", "rm": "rm_CH"}


def load_gold(date):
    path = os.path.join(GOLD_DIR, f"aligned_{date}.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def batched_sims(q_emb, c_emb, batch=32):
    """Full (Q,C) cosine matrix. NOTE: retriever.cosine_sim_matrix() returns
    only row [0] (it is built for a single query), so it cannot be used here."""
    qn = q_emb / (np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-9)
    cn = c_emb / (np.linalg.norm(c_emb, axis=1, keepdims=True) + 1e-9)
    sims = np.zeros((qn.shape[0], cn.shape[0]), dtype=np.float32)
    for s in range(0, qn.shape[0], batch):
        sims[s:s + batch] = qn[s:s + batch] @ cn.T
    return sims


def rank_of(sims, gold_col, exclude_self=False):
    ranks = []
    for i, g in enumerate(gold_col):
        scores = sims[i].copy()
        if exclude_self:
            scores[i] = -np.inf
        order = np.argsort(-scores)
        ranks.append(int(np.where(order == g)[0][0]))
    return ranks


def report(name, ranks, n_corpus):
    r1 = sum(1 for r in ranks if r < 1) / len(ranks)
    r5 = sum(1 for r in ranks if r < 5) / len(ranks)
    print(f"  {name:<24} n={len(ranks):<4} R@1={r1:.3f}  R@5={r5:.3f}   "
          f"(chance R@1={1.0/n_corpus:.3f}, mean gold rank="
          f"{np.mean(ranks)+1:.1f}/{n_corpus})")
    return r1, r5


def eval_cross_lingual(ret, date, mode, min_len=80):
    """Query in DE, retrieve the aligned FR/IT/RM counterpart from the full
    foreign-language corpus of that booklet."""
    rows = load_gold(date)
    rows = [r for r in rows if all(len(r.get(l, "").strip()) > min_len
                                   for l in ("de", "fr", "it"))]
    if len(rows) < 10:
        print(f"\n--- {date}: only {len(rows)} usable groups, skipped")
        return

    print(f"\n--- {date}: {len(rows)} aligned segment groups "
          f"(mode={mode}) ---")
    for tgt in ("fr", "it", "rm"):
        # Skip languages the booklet does not actually contain. The 1977
        # gold file has no Romansh at all (0/169 groups); scoring it would
        # just rank empty strings and report noise as if it were a result.
        have_tgt = [r for r in rows if len(r.get(tgt, "").strip()) > min_len]
        if len(have_tgt) < 10:
            print(f"  DE query -> {tgt.upper()} corpus    "
                  f"skipped ({len(have_tgt)} usable {tgt.upper()} segments)")
            continue
        q_texts = [r["de"] for r in have_tgt]
        c_texts = [r[tgt].strip() for r in have_tgt]
        c_ad = ADAPTER[tgt] if mode == "mismatched" else ADAPTER["de"]
        q_emb = ret.encode(q_texts, lang_code=ADAPTER["de"])
        c_emb = ret.encode(c_texts, lang_code=c_ad)
        sims = batched_sims(q_emb, c_emb)
        gold = list(range(len(q_texts)))
        ranks = rank_of(sims, gold)
        report(f"DE query -> {tgt.upper()} corpus", ranks, len(c_texts))


def eval_same_lang_control(ret, date, min_len=80):
    """Control task: each DE query's true match is its own ALIGNED German
    duplicate is excluded, so instead we query a short snippet taken from a
    passage and check it retrieves that passage. Confirms the encoder ranks
    semantic matches well when language is not a factor."""
    rows = load_gold(date)
    rows = [r for r in rows if len(r.get("de", "").strip()) > min_len]
    if len(rows) < 10:
        return
    # probe = first sentence of the passage, corpus = whole passages,
    # correct hit = the passage it came from (self-match removed).
    probes, corpus, gold = [], [], []
    for i, r in enumerate(rows):
        text = r["de"].strip()
        probe = text[:60]
        if len(probe) < 40:
            continue
        probes.append(probe)
        corpus.append(text)
        gold.append(i)
    if len(probes) < 10:
        return
    print(f"\n--- SAME-LANG control {date}: DE snippet -> DE passage "
          f"(self excluded) ---")
    q_emb = ret.encode(probes, lang_code=ADAPTER["de"])
    c_emb = ret.encode(corpus, lang_code=ADAPTER["de"])
    sims = batched_sims(q_emb, c_emb)
    ranks = rank_of(sims, gold, exclude_self=True)
    report("DE->DE source recovery", ranks, len(corpus))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="mismatched",
                    choices=["mismatched", "uniform", "same-lang"])
    args = ap.parse_args()

    t0 = time.time()
    ret = Retriever()
    print(f"\nMode: {args.mode}")
    for date in ("1977-06-12", "1985-12-01", "2007-03-11"):
        if args.mode == "same-lang":
            eval_same_lang_control(ret, date)
        else:
            eval_cross_lingual(ret, date, args.mode)
    print(f"\ntotal: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
