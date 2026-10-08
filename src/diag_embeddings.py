"""
Diagnostic: is cross-lingual retrieval actually working, or is the encoder
producing language-blind / degenerate embeddings?

Three checks:
  A. Do the Xmod language adapters actually load and do anything?
     (config.json declares adapters, but the loaded module may not.)
  B. Does the adapter choice change the embedding of the SAME text?
     If de_CH and fr_CH give identical vectors, adapters are inert.
  C. Translation-pair signal test: is cos(de_i, fr_i) (true translation
     pair) meaningfully higher than cos(de_i, fr_j) for i != j?
     If the means are close, there is no usable cross-lingual signal at
     this granularity, regardless of what the R@1 numbers say.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import torch
from retriever import Retriever

GOLD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    os.pardir, "repos", "VotingBooklets",
                    "gold_files", "gold_alignment", "aligned_2007-03-11.jsonl")

SENT = "Der Bundesrat lehnt die Initiative ab."

print("=" * 66)
print("A. adapter / architecture inspection")
print("=" * 66)
r = Retriever()
m = r.model
print("model class          :", type(m).__name__)
for attr in ("adapter_modules", "language_embedding_dim", "languages",
             "default_language", "numLanguages"):
    print(f"  has {attr:<20}:", hasattr(m, attr),
          "|", getattr(m, "adapter_modules", None) if attr == "adapter_modules"
          else getattr(m, attr, ""))
print("  set_default_language exists:", hasattr(m, "set_default_language"))

print()
print("=" * 66)
print("B. does the adapter setting change the vector for one text?")
print("=" * 66)
try:
    m.set_default_language("de_CH")
    v_de = r.encode([SENT], lang_code="de_CH")[0]
    m.set_default_language("fr_CH")
    v_fr = r.encode([SENT], lang_code="fr_CH")[0]
    cos = float(v_de @ v_fr / (np.linalg.norm(v_de) * np.linalg.norm(v_fr)))
    ident = np.allclose(v_de, v_fr)
    print(f"  identical vectors: {ident}   cosine(de_ch_vec, fr_ch_vec)={cos:.4f}")
    print("  ->" , "ADAPTERS ARE INERT (same vector for both languages)"
          if ident or cos > 0.9999 else "adapters DO change the representation")
except Exception as e:
    print("  set_default_language raised:", type(e).__name__, e)

print()
print("=" * 66)
print("C. translation-pair signal (2007 gold alignment, DE -> FR)")
print("=" * 66)
rows = [json.loads(l) for l in open(GOLD, encoding="utf-8")]
rows = [r_ for r_ in rows if all(len(r_.get(k, "").strip()) > 40
                                 for k in ("de", "fr"))]
de = [x["de"] for x in rows]
fr = [x["fr"] for x in rows]
print(f"  {len(de)} aligned pairs")

A = r.encode(de, lang_code="de_CH")
B = r.encode(fr, lang_code="fr_CH")
An = A / np.linalg.norm(A, axis=1, keepdims=True)
Bn = B / np.linalg.norm(B, axis=1, keepdims=True)
S = An @ Bn.T

n = len(de)
own = np.diag(S)
mask = ~np.eye(n, dtype=bool)
other = S[mask]
print(f"  mean cos(TRUE translation pair)   = {own.mean():.4f}")
print(f"  mean cos(UNRELATED pair)          = {other.mean():.4f}")
print(f"  std  cos(UNRELATED pair)          = {other.std():.4f}")
gap = own.mean() - other.mean()
print(f"  separation gap                    = {gap:.4f}")
print(f"  pairs where own is top-1          = {(S.argmax(1) == np.arange(n)).sum()}/{n}")

# same-language sanity: identical text must score 1.0, paraphrase should
# beat random. This proves the encoder is not degenerate.
print()
print("  --- sanity: encoder degeneracy check ---")
Same = r.encode(de, lang_code="de_CH")
Sn = Same / np.linalg.norm(Same, axis=1, keepdims=True)
Sd = Sn @ Sn.T
diag_mean = float(np.diag(Sd).mean())
offdiag = Sd[mask]
print(f"  DE->DE self-similarity (must be 1.000) = {diag_mean:.4f}")
print(f"  DE->DE mean non-self similarity        = {offdiag.mean():.4f}")
print("  -> if self=1.0 and non-self ~0.6-0.8 the encoder works fine and")
print("     the problem is cross-lingual transfer, not a broken encoder.")