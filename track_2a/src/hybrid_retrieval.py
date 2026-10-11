"""
Shared retrieval structures for the booklet PDF corpus (Track 2A Priority 2).

Contents
--------
* `norm_text` / `BM25` - moved verbatim from eval_e2e.py so the hybrid and
  two-stage paths reuse ONE lexical scorer instead of a second implementation.
  `BM25.top_k` gained a `restrict` argument that only narrows the documents
  scored; with `restrict=None` the ranking is identical to the previously
  measured `lexical` baseline (same k1/b, same idf, stable tie order).
* `TwoStageRetriever` - two candidate setups, both fused with Reciprocal Rank
  Fusion (RRF):
    mode="global":      fuse global BM25 candidates with global dense
                        candidates (no booklet routing).
    mode="two_stage":   stage 1 ranks the 60 booklets with RRF over
                        (a) BM25 on whole-booklet text and (b) mean-of-top-3
                        passage cosine per booklet; stage 2 gathers lexical +
                        dense passage candidates ONLY from the top `doc_top_n`
                        booklets, fuses them with RRF (weighted by the
                        booklet's routing rank), and optionally caps passages
                        per booklet (`per_doc_cap` - counters the parallel-
                        language duplicate problem, report §7B).
* Index cache - corpus embeddings are cached under data/cache/ keyed by a
  hash over (model id, batch size, per-passage lang+text). Encoding 16.6k
  passages is the expensive part; vectors depend on batch composition
  (padding), hence batch size is part of the key.

Integrity: ranking consults claim text only (optionally translated).
`booklet_url`, `reference_string` and gold labels are NEVER read here -
document routing at prediction time is done by the retriever itself, which
is exactly what `doc_routing_top1` measures in eval_e2e.py.
"""
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np

from config import BATCH_SIZE, DATA_DIR, EMBEDDING_MODEL


# ------------------------------------------------------------------ lexical

def norm_text(s: str) -> str:
    """Aggressive normalisation: NFKC, lowercase, alnum-only, spaces squashed.

    Used for BOTH sides of the evidence<->passage matcher so PDF layout noise
    (ligatures, doubled spaces, hyphenation artefacts) cannot break matching.
    """
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


class BM25:
    """Minimal BM25 (k1=1.2, b=0.75).

    `top_k(..., restrict=...)` scores only the given document indices;
    without `restrict` results are byte-identical to the original
    eval_e2e.py implementation (kept so the `lexical` baseline stays
    reproducible).

    Tokenisation protocol is explicit (2026-10-10): the query side always
    uses norm_text, while `norm_docs=False` (protocol "lex-asym-v1")
    indexes docs as RAW whitespace tokens. That asymmetry is an acknowledged
    defect preserved only for comparability with the measured §5.4 ranking,
    NOT a design claim. `norm_docs=True` ("lex-sym-v2") normalises both
    sides identically and is the deployable form.
    """

    def __init__(self, texts, k1=1.2, b=0.75, norm_docs=False):
        self.k1, self.b = k1, b
        self.protocol = "lex-sym-v2" if norm_docs else "lex-asym-v1"
        self.doc_tok = [norm_text(t).split() if norm_docs else t.split()
                        for t in texts]
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

    def top_k(self, query: str, k: int, restrict=None):
        allowed = None
        if restrict is not None:
            allowed = restrict if isinstance(restrict, set) else set(restrict)
        scores = {}
        for t in norm_text(query).split():
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.index.get(t, ()):
                if allowed is not None and i not in allowed:
                    continue
                f = self.tf[i][t]
                denom = f + self.k1 * (1 - self.b + self.b
                                       * self.doc_len[i] / self.avg_len)
                scores[i] = scores.get(i, 0.0) + idf * f * (self.k1 + 1) / denom
        top = sorted(scores.items(), key=lambda x: -x[1])[:k]
        return top


# ---------------------------------------------------------------------- rrf

def rrf_fuse(ranked_lists, k: float = 60.0, weights=None):
    """Reciprocal Rank Fusion over several ranked [(id, score)] lists.

    score(item) = sum over lists of w_list / (k + rank_in_list). Returns
    [(id, score)] in descending order; ties keep first-seen order (stable).
    `weights` lets the caller decay contributions of weaker sources (e.g.
    stage-2 lists coming from a low-ranked booklet).
    """
    scores = {}
    for li, lst in enumerate(ranked_lists):
        w = 1.0 if weights is None else weights[li]
        for rank, (item, _s) in enumerate(lst, 1):
            scores[item] = scores.get(item, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])


# ------------------------------------------------------------ two-stage

class TwoStageRetriever:
    """See module docstring. Pure numpy + BM25; query embeddings/similarity
    rows are supplied by the caller so eval can batch-encode queries."""

    def __init__(self, corpus, corpus_mat=None, mode="two_stage",
                 doc_top_n=3, cand_per_source=8, cand_global=50,
                 per_doc_cap=0, rrf_k=60.0,
                 use_lexical=True, use_dense=True, doc_decay=1.0,
                 lex_protocol="asym"):
        assert mode in ("two_stage", "global")
        assert lex_protocol in ("asym", "sym"), lex_protocol
        self.mode = mode
        self.lex_protocol = lex_protocol
        self.doc_top_n = doc_top_n
        self.cand_per_source = cand_per_source
        self.cand_global = cand_global
        self.per_doc_cap = per_doc_cap
        self.rrf_k = rrf_k
        self.use_lexical = use_lexical
        self.doc_decay = doc_decay
        self.corpus = corpus

        self.doc_ids = sorted({r["doc_id"] for r in corpus})
        doc_of = {d: i for i, d in enumerate(self.doc_ids)}
        self.doc_passages = [[] for _ in self.doc_ids]
        for i, r in enumerate(corpus):
            self.doc_passages[doc_of[r["doc_id"]]].append(i)
        self.doc_passage_sets = [set(idxs) for idxs in self.doc_passages]

        if use_lexical:
            # `lex_protocol` selects the tokenisation contract for BOTH the
            # booklet router and the stage-2 passage list. "asym" is the
            # historically reported behaviour (raw doc tokens vs normalised
            # query): asymmetric, and wrong whenever a query token differs
            # from its indexed form only by case or punctuation. It stays the
            # default so §5.4's recorded numbers remain reproducible; "sym"
            # is the corrected, deployable channel.
            norm = lex_protocol == "sym"
            self.passage_bm25 = BM25([r["text"] for r in corpus],
                                     norm_docs=norm)
            if mode == "two_stage":
                doc_texts = [" ".join(corpus[i]["text"] for i in idxs)
                             for idxs in self.doc_passages]
                self.doc_bm25 = BM25(doc_texts, norm_docs=norm)

        self.use_dense = bool(use_dense and corpus_mat is not None)
        self.mat = None
        if self.use_dense:
            mat = np.asarray(corpus_mat, dtype=np.float32)
            self.mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)

    # -- helpers ---------------------------------------------------------
    def _dense_top(self, sims, indices, k):
        """Top-k (index, sim) over the given passage indices of one query."""
        s = sims[indices]
        if len(s) > k:
            order = np.argpartition(-s, k - 1)[:k]
        else:
            order = np.arange(len(s))
        order = sorted(order, key=lambda j: -float(s[j]))
        return [(int(indices[j]), float(s[j])) for j in order]

    def _cap(self, fused, k):
        if not self.per_doc_cap:
            return fused[:k]
        out, seen = [], Counter()
        for idx, s in fused:
            d = self.corpus[idx]["doc_id"]
            if seen[d] >= self.per_doc_cap:
                continue
            seen[d] += 1
            out.append((idx, s))
            if len(out) >= k:
                break
        return out

    # -- main entry ------------------------------------------------------
    def retrieve(self, query: str, k: int = 5, sims=None, query_emb=None):
        """Return a ranked [(passage_index, fusion_score)] list of length k.

        `sims`: precomputed cosine similarity row (corpus-wide) for this
        query; computed from `query_emb` if absent. Eval batches the rows
        (Q @ corpus.T) to keep full-set runs fast.
        """
        if sims is None and self.use_dense:
            if query_emb is None:
                raise ValueError("dense mode needs sims or query_emb")
            q = query_emb / (np.linalg.norm(query_emb) + 1e-9)
            sims = self.mat @ q

        if self.mode == "global":
            lists = []
            if self.use_lexical:
                lists.append(self.passage_bm25.top_k(query, self.cand_global))
            if self.use_dense and sims is not None:
                top = np.argsort(-sims)[:self.cand_global]
                lists.append([(int(j), float(sims[j])) for j in top])
            return self._cap(rrf_fuse(lists, self.rrf_k), k)

        # ---- two-stage: route booklets first --------------------------
        doc_lists = []
        if self.use_lexical:
            doc_lists.append(self.doc_bm25.top_k(query, len(self.doc_ids)))
        if self.use_dense and sims is not None:
            scored = []
            for d, idxs in enumerate(self.doc_passages):
                s = sims[idxs]
                top = np.partition(s, -3)[-3:] if len(s) >= 3 else s
                scored.append((d, float(top.mean())))
            scored.sort(key=lambda x: -x[1])
            doc_lists.append(scored)
        chosen = [d for d, _
                  in rrf_fuse(doc_lists, self.rrf_k)][:self.doc_top_n]

        lists, weights = [], []
        for rank, d in enumerate(chosen):
            w = 1.0 / (1.0 + self.doc_decay * rank)
            idxs = self.doc_passage_sets[d]
            if self.use_lexical:
                lists.append(self.passage_bm25.top_k(
                    query, self.cand_per_source, restrict=idxs))
                weights.append(w)
            if self.use_dense and sims is not None:
                lists.append(self._dense_top(
                    sims, self.doc_passages[d], self.cand_per_source))
                weights.append(w)
        return self._cap(rrf_fuse(lists, self.rrf_k, weights=weights), k)


# -------------------------------------------------------------- index cache

CACHE_DIR = DATA_DIR / "cache"


def index_cache_key(corpus, model: str = EMBEDDING_MODEL,
                    batch: int = BATCH_SIZE) -> str:
    """Hash over everything that affects cached vectors (model, batching,
    per-passage language + text). Order-sensitive on purpose: the cache is
    only valid for the exact corpus build it was produced from."""
    h = hashlib.sha256()
    h.update(f"{model}|{batch}".encode())
    for r in corpus:
        h.update(r["text"].encode("utf-8"))
        h.update(b"\x00")
        h.update(r["lang"].encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def load_index(key: str, n_expected=None):
    """Return cached corpus embeddings, or None when there is no cache.

    Integrity gate (2026-10-10): a cache is trusted only if its shape
    matches the corpus currently loaded, every value is finite, and -
    when a provenance manifest exists - the manifest agrees on rows,
    dimension and model id. A stale or torn cache RAISES instead of
    silently ranking on garbage vectors; delete it or rebuild explicitly.
    """
    p = CACHE_DIR / f"emb_{key}.npy"
    if not p.exists():
        return None
    mat = np.load(p)
    problems = []
    if mat.ndim != 2:
        problems.append(f"ndim={mat.ndim}")
    else:
        if n_expected is not None and mat.shape[0] != n_expected:
            problems.append(f"rows={mat.shape[0]} but corpus has "
                            f"{n_expected}")
        if not np.isfinite(mat).all():
            problems.append("contains non-finite values")
    mp = CACHE_DIR / f"emb_{key}.json"
    if mp.exists() and mat.ndim == 2:
        man = json.loads(mp.read_text(encoding="utf-8"))
        if man.get("n") != mat.shape[0] or man.get("dim") != mat.shape[1]:
            problems.append("manifest disagrees with array shape")
        if man.get("model") != EMBEDDING_MODEL:
            problems.append(f"manifest model {man.get('model')!r} != "
                            f"current {EMBEDDING_MODEL!r}")
    if problems:
        raise ValueError(
            f"index cache emb_{key}.npy is not trustworthy "
            f"({'; '.join(problems)}); delete data/cache/emb_{key}.* and "
            "rebuild the index explicitly")
    return mat


def save_index(key: str, mat):
    """Atomic write (tmp + replace) of matrix + provenance manifest, so an
    interrupted build can never leave a torn cache that passes as a hit."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    mat = np.asarray(mat, dtype=np.float32)
    npy = CACHE_DIR / f"emb_{key}.npy"
    tmp = CACHE_DIR / f"emb_{key}.npy.tmp"
    with tmp.open("wb") as fh:
        np.save(fh, mat)
    tmp.replace(npy)
    man = CACHE_DIR / f"emb_{key}.json"
    man_tmp = CACHE_DIR / f"emb_{key}.json.tmp"
    man_tmp.write_text(json.dumps({
        "key": key,
        "n": int(mat.shape[0]),
        "dim": int(mat.shape[1]) if mat.ndim == 2 else None,
        "model": EMBEDDING_MODEL,
        "batch": BATCH_SIZE,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }), encoding="utf-8")
    man_tmp.replace(man)


# --------------------------------------------------- CLI query-language aid

# Tiny function-word heuristic so the CLI (which has NO gold evidence
# language) can pick a query adapter without oracle information. Anything
# inconclusive - including English - falls back to "de" (de_CH adapter),
# matching the historical default.
_FUNC_WORDS = {
    "de": {"der", "die", "das", "und", "fur", "mit", "nicht", "werden",
           "bundesrat", "abstimmung", "vorlage", "soll", "auch", "wie",
           "von", "ist", "bei", "auf"},
    "fr": {"le", "la", "les", "et", "pour", "dans", "qui", "que", "est",
           "ne", "pas", "ou", "au", "aux", "federal", "votation"},
    "it": {"il", "la", "di", "e", "per", "che", "non", "con", "una",
           "del", "della", "nella", "votazione", "federale"},
}


def detect_query_language(text: str) -> str:
    toks = norm_text(text).split()
    best, best_hits = "de", 0
    for lang, words in _FUNC_WORDS.items():
        hits = sum(1 for t in toks if t in words)
        if hits > best_hits:
            best, best_hits = lang, hits
    return best

