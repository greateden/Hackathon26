"""
Retriever: Embed-based passage retrieval using Sentence SwissBERT.

Given a claim, finds the most relevant passages from the voting booklet corpus.
"""
import time
import glob
import os
import sys
import numpy as np
import torch
from pathlib import Path
from transformers import AutoModel, AutoTokenizer, PreTrainedTokenizerFast
from typing import Dict, List

from config import EMBEDDING_MODEL, BATCH_SIZE, TOP_K, MIN_SIMILARITY


def profile_log(event: str, **fields):
    """Write opt-in, non-sensitive performance diagnostics to stderr."""
    if os.environ.get("VOTELENS_PROFILE") == "1":
        details = " ".join(f"{key}={value}" for key, value in fields.items())
        print(f"[votelens-profile] {event}" + (f" {details}" if details else ""),
              file=sys.stderr, flush=True)


def cosine_sim_matrix(query_emb: np.ndarray, corpus_emb: np.ndarray) -> np.ndarray:
    """Cosine similarity between query (1,D) and corpus (N,D). Returns (N,)."""
    q_norm = query_emb / (np.linalg.norm(query_emb, axis=1, keepdims=True) + 1e-9)
    c_norm = corpus_emb / (np.linalg.norm(corpus_emb, axis=1, keepdims=True) + 1e-9)
    return (q_norm @ c_norm.T)[0]


def load_tokenizer_compat(model_name: str):
    """
    Workaround for a transformers 5.x bug when loading sentence-swissbert's
    tokenizer via AutoTokenizer. Falls back to loading tokenizer.json directly.
    """
    try:
        return AutoTokenizer.from_pretrained(model_name)
    except TypeError:
        pass

    local_tokenizer = Path(model_name) / "tokenizer.json"
    cache = Path.home() / ".cache/huggingface/hub"
    slug = "models--" + model_name.replace("/", "--")
    matches = sorted(glob.glob(str(cache / slug / "snapshots" / "*" / "tokenizer.json")))
    if local_tokenizer.is_file():
        tok_file = local_tokenizer
    elif not matches:
        try:
            from huggingface_hub import hf_hub_download
            tok_file = Path(hf_hub_download(repo_id=model_name, filename="tokenizer.json"))
        except Exception as e:
            raise RuntimeError(
                f"Cannot load tokenizer for {model_name}. AutoTokenizer hit the "
                f"transformers 5.x AddedToken bug and no tokenizer.json is available: {e}"
            )
    else:
        tok_file = Path(matches[0])

    tok = PreTrainedTokenizerFast(tokenizer_file=str(tok_file))
    # Configure special tokens via the proper API (setting _pad_token alone
    # does not enable padding). We reconstruct the special-token set matching
    # the model's tokenizer_config.json.
    tok.add_special_tokens({
        "bos_token": "<s>",
        "eos_token": "</s>",
        "unk_token": "<unk>",
        "sep_token": "</s>",
        "pad_token": "<pad>",
        "cls_token": "<s>",
    })
    tok.model_max_length = 512
    return tok


LANG_TO_ADAPTER = {
    "de": "de_CH",
    "fr": "fr_CH",
    "it": "it_CH",
    "rm": "rm_CH",
    "en": "de_CH",  # English queries: use the de_CH adapter (SwissBERT's dominant language)
}


class Retriever:
    """Embedding-based retriever using Sentence SwissBERT (or any AutoModel)."""

    def __init__(self, model_name: str = EMBEDDING_MODEL, device: str = None):
        if device is None:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"Loading embedding model: {model_name} on {self.device}", file=sys.stderr)
        t0 = time.time()
        self.tokenizer = load_tokenizer_compat(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"Model loaded in {time.time() - t0:.1f}s", file=sys.stderr)
        profile_log(
            "embedding_threads",
            torch_intra=torch.get_num_threads(),
            torch_inter=torch.get_num_interop_threads(),
            omp=os.environ.get("OMP_NUM_THREADS", "unset"),
            mkl=os.environ.get("MKL_NUM_THREADS", "unset"),
            openblas=os.environ.get("OPENBLAS_NUM_THREADS", "unset"),
        )

        self.corpus_embeddings: np.ndarray | None = None
        self.corpus_records: List[Dict] = []

    def set_default_language(self, lang_code: str):
        """Set the Xmod adapter language if the model supports it."""
        try:
            self.model.set_default_language(lang_code)
        except Exception:
            pass

    @torch.no_grad()
    def encode(self, texts: List[str], lang_code: str = "de_CH") -> np.ndarray:
        """Encode texts via mean pooling (matches the official SentenceSwissBERT recipe)."""
        started = time.perf_counter()
        self.set_default_language(lang_code)
        all_emb = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            inputs = self.tokenizer(
                batch, padding=True, truncation=True,
                return_tensors="pt", max_length=512,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            tok_emb = outputs.last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).float()
            emb = (torch.sum(tok_emb * mask, 1) /
                   torch.clamp(mask.sum(1), min=1e-9)).cpu().numpy()
            all_emb.append(emb)
        embeddings = np.vstack(all_emb)
        profile_log("embedding", count=len(texts), adapter=lang_code,
                    duration_s=f"{time.perf_counter() - started:.3f}")
        return embeddings

    def build_index(self, corpus: List[Dict]):
        """Build the embedding index for the full corpus, grouping by language."""
        print(f"Building index for {len(corpus)} passages...")
        t0 = time.time()
        texts = [r["text"] for r in corpus]

        by_lang: Dict[str, List[int]] = {}
        for i, r in enumerate(corpus):
            by_lang.setdefault(r["lang"], []).append(i)

        # Store (index, vector) pairs, then sort by index to preserve order
        pairs: List[tuple] = []
        for lang, indices in by_lang.items():
            lang_texts = [texts[i] for i in indices]
            lang_code = LANG_TO_ADAPTER.get(lang, "de_CH")
            lang_emb = self.encode(lang_texts, lang_code=lang_code)
            for k, i in enumerate(indices):
                pairs.append((i, lang_emb[k]))

        pairs.sort(key=lambda x: x[0])
        self.corpus_embeddings = np.stack([e for _, e in pairs], axis=0).astype(np.float32)
        self.corpus_records = corpus
        print(f"Index built in {time.time() - t0:.1f}s, shape: {self.corpus_embeddings.shape}")

    def retrieve(
        self,
        claim: str,
        top_k: int = TOP_K,
        filter_year: str = None,
        filter_lang: str = None,
    ) -> List[Dict]:
        """
        Retrieve top-k passages most relevant to the claim.

        Args:
            claim: The natural-language claim to verify.
            top_k: Number of passages to return.
            filter_year: Only search a specific year's documents (e.g. "2007").
            filter_lang: Only search a specific language (de/fr/it/rm).

        Returns:
            List of passage dicts with `score` field, sorted by relevance.
        """
        if self.corpus_embeddings is None:
            raise RuntimeError("Index not built. Call build_index() first.")

        # Encode the claim with the de_CH adapter and compare against passages
        # encoded with their OWN language adapter (see build_index). Measured on
        # the gold parallel corpus (eval_retrieval.py), per-language adapters beat
        # encoding everything with de_CH (e.g. DE->IT R@1 on 1977: 0.851 vs 0.617).
        # Caveat: this path is measured for text-to-translation matching. Claim->
        # evidence retrieval from English queries is much weaker (see report §5.3);
        # translating the claim into the corpus language before encoding is the
        # next thing to try.
        claim_emb = self.encode([claim], lang_code="de_CH")

        sims = cosine_sim_matrix(claim_emb, self.corpus_embeddings)

        indices = list(range(len(self.corpus_records)))
        if filter_year:
            indices = [i for i in indices if self.corpus_records[i]["year"] == filter_year]
        if filter_lang:
            indices = [i for i in indices if self.corpus_records[i]["lang"] == filter_lang]

        scored = [(i, float(sims[i])) for i in indices if sims[i] >= MIN_SIMILARITY]
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

        results = []
        for idx, score in scored:
            record = self.corpus_records[idx]
            results.append({**record, "score": score})
        return results


def build_retriever(corpus: List[Dict]) -> Retriever:
    """Convenience: create a retriever and build its index in one call."""
    retriever = Retriever()
    retriever.build_index(corpus)
    return retriever
