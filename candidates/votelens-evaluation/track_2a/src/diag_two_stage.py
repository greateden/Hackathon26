"""Diagnostic: where does two-stage lose recall - routing or fusion?

Counts, over the dev-60 sample: items with empty top-5 (plumbing check),
how often the gold booklet is among the 3 routed booklets, and whether the
gold passage is retrievable GIVEN correct routing. Run from src/.
"""
import json
import sys

sys.path.insert(0, '.')

from hybrid_retrieval import TwoStageRetriever, rrf_fuse
from fetch_booklets import load_dataset
from sampling import balanced_sample
from eval_e2e import run_evidence_matching

corpus = json.load(open('../data/booklets/corpus.json'))
recs = balanced_sample(load_dataset(), 60, seed=42)
gold_map, cov, _ = run_evidence_matching(recs, corpus)
ts = TwoStageRetriever(corpus, mode='two_stage', use_dense=False)

scored = empty = routed_ok = hit_in_routed = 0
miss_routed = []
for n, r in enumerate(recs):
    gm = gold_map[n]
    if not gm['gold']:
        continue
    scored += 1
    top = [i for i, _ in ts.retrieve(r['claim'], 5)]
    if not top:
        empty += 1
        continue
    doc_lists = [ts.doc_bm25.top_k(r['claim'], len(ts.doc_ids))]
    chosen = [d for d, _ in rrf_fuse(doc_lists, 60)][:3]
    gold_docs = {corpus[i]['doc_id'] for i in gm['gold']}
    chosen_ids = {ts.doc_ids[d] for d in chosen}
    if chosen_ids & gold_docs:
        routed_ok += 1
        if set(top) & gm['gold']:
            hit_in_routed += 1
    elif not (set(top) & gm['gold']):
        miss_routed.append((r['claim'][:60], sorted(chosen_ids),
                            sorted(gold_docs)))

print(f'scored={scored} empty={empty} '
      f'gold_booklet_in_top3={routed_ok} '
      f'gold_found|correct_booklets={hit_in_routed}/{routed_ok}')
print('sample routing misses:')
for c, ch, g in miss_routed[:4]:
    print('  claim:', c)
    print('    routed:', ch)
    print('    gold  :', g)