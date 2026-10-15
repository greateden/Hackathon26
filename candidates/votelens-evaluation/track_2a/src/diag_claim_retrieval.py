"""
Diagnostic: for a claim whose decisive sentence exists verbatim in the
corpus, does retrieval actually surface it?

Claim 1 of data/example_claims.json expects `entailment`, and the booklet
literally says "Bundesrat und Parlament lehnen die Initiative ab." (passage
de_2007_002). The MLX run returned `neutral`, so either
  (a) retrieval never surfaced de_2007_002 -> retrieval problem, or
  (b) it was surfaced and the model still said neutral -> judge problem.

We probe the same fact with an English claim, a German claim, and the
verbatim German sentence, to separate cross-lingual transfer from
vocabulary overlap.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from ingest import build_corpus
from retriever import Retriever, cosine_sim_matrix

TARGET = "de_2007_002"

PROBES = [
    ("EN claim (as written in example_claims)",
     "The Federal Council and Parliament recommend rejecting the single "
     "health insurance fund initiative."),
    ("DE claim (translated)",
     "Der Bundesrat und das Parlament empfehlen, die Einheitskassen-"
     "Initiative abzulehnen."),
    ("DE verbatim decisive sentence",
     "Bundesrat und Parlament lehnen die Initiative ab."),
    ("EN keyword-free paraphrase",
     "What do the authorities recommend voters do about this initiative?"),
]


def main():
    corpus = build_corpus()
    ret = Retriever()
    ret.build_index(corpus)
    ids = [p["id"] for p in corpus]
    ti = ids.index(TARGET)
    print(f"\ncorpus: {len(corpus)} passages, target index {ti}\n")

    for name, q in PROBES:
        emb = ret.encode([q], lang_code="de_CH")
        sims = cosine_sim_matrix(emb, ret.corpus_embeddings)
        order = np.argsort(-sims)
        rank = int(np.where(order == ti)[0][0])
        top = order[:5]
        print(f"--- {name}")
        print(f"    rank of {TARGET}: {rank + 1}  (cos={sims[ti]:.3f})")
        for pos, k in enumerate(top, 1):
            rec = corpus[k]
            snippet = rec["text"][:72].replace("\n", " ")
            flag = "  <== TARGET" if k == ti else ""
            print(f"      #{pos} [{rec['lang']}] {rec['id']} "
                  f"cos={sims[k]:.3f}  {snippet}{flag}")
        print()


if __name__ == "__main__":
    main()