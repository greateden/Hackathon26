"""Quick smoke test of the full pipeline."""
import sys, time, os
sys.path.insert(0, os.path.dirname(__file__))

from ingest import build_corpus
from retriever import build_retriever

print("=== Building corpus ===")
corpus = build_corpus()
print(f"Corpus: {len(corpus)} passages")

print("\n=== Downloading + building embedding index ===")
t0 = time.time()
retriever = build_retriever(corpus)
print(f"Total time: {time.time()-t0:.1f}s")

print("\n=== Test retrieval ===")
test_claim = "The Federal Council recommends rejecting the single health insurance fund."
print(f"Query: {test_claim}")
results = retriever.retrieve(test_claim, top_k=3, filter_year="2007")
print(f"Found {len(results)} passages:")
for r in results:
    print(f"  [{r['lang']}] sim={r['score']:.3f}  {r['text'][:120]}")

print("\n=== German claim ===")
test_de = "Der Bundesrat lehnt die Einheitskasse ab."
results2 = retriever.retrieve(test_de, top_k=3, filter_year="2007")
for r in results2:
    print(f"  [{r['lang']}] sim={r['score']:.3f}  {r['text'][:120]}")

print("\n=== French claim ===")
test_fr = "Le Conseil federal refuse la caisse unique."
results3 = retriever.retrieve(test_fr, top_k=3, filter_year="2007")
for r in results3:
    print(f"  [{r['lang']}] sim={r['score']:.3f}  {r['text'][:120]}")