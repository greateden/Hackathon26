"""
Booklet PDF ingestion: turn the booklet PDFs referenced by the official eval
set into a retrieval corpus built ONLY from original documents.

Stages (all resumable, rerun-safe):
  1. discover  unique booklet PDFs via the `booklet_url` field of
               data/eval/mnli_swiss_v1.1.jsonl (60 URLs: 20 DE / 20 FR / 20 IT)
  2. fetch     download PDFs into data/booklets/pdf/ (skip existing, verify
               the %PDF magic bytes so HTML error pages never poison the cache)
  3. extract   PDF -> text with `pdftotext` (Poppler); fallback PyMuPDF
  4. index     text -> passage records written to data/booklets/corpus.json

Integrity rule (Track 2A): the dataset's `reference_string` values are ORACLE
evidence. They are never copied into the corpus. Retrieval must find the
answer in the original PDFs, the same way the end-to-end task requires.

Usage:
  python3 fetch_booklets.py --list            # show the plan + local cache state
  python3 fetch_booklets.py                   # fetch + extract + index (all)
  python3 fetch_booklets.py --limit 6 --out /tmp/booklet-smoke.json
  python3 fetch_booklets.py --skip-fetch      # re-extract/re-index only
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from config import (BOOKLET_CORPUS_JSON, BOOKLET_PDF_DIR, BOOKLET_TEXT_DIR,
                    DATA_DIR)

DATASET_PATH = DATA_DIR / "eval" / "mnli_swiss_v1.1.jsonl"
USER_AGENT = "HackApertus2A-research/1.0 (claim-verification research tool)"
TIMEOUT_S = 90
POLITE_DELAY_S = 0.3


def load_dataset(path: Path = DATASET_PATH):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def booklet_key(url: str) -> str:
    """Stable local identity for one booklet PDF.

    https://www.bk.admin.ch/dam/fr/sd-web/MDRXrtFaVPNG/2026-03-08_explications...pdf
      -> 2026-03-08_fr_explications...
    """
    parts = url.rstrip("/").split("/")
    # The language segment sits between /dam/ and /sd-web/; match it anywhere
    # rather than trusting a fixed index.
    lang = next((p for p in parts if p in ("de", "fr", "it", "rm")), "xx")
    name = parts[-1].replace(".pdf", "")
    return f"{name}_{lang}"


def pdf_path(url: str) -> Path:
    return BOOKLET_PDF_DIR / (booklet_key(url) + ".pdf")


def txt_path(url: str) -> Path:
    return BOOKLET_TEXT_DIR / (booklet_key(url) + ".txt")


def list_booklets(dataset) -> list:
    """One entry per unique booklet_url, with the number of eval items it serves."""
    by_url = {}
    for rec in dataset:
        by_url.setdefault(rec["booklet_url"], []).append(rec)
    entries = []
    for url, recs in sorted(by_url.items()):
        entries.append({
            "url": url,
            "key": booklet_key(url),
            "n_items": len(recs),
            "langs": sorted({r["reference_language"] for r in recs}),
        })
    return entries


def fetch_pdf(url: str, dest: Path) -> str:
    """Download one PDF. Returns 'cached' | 'ok' | 'bad' | 'error:<msg>'."""
    if dest.exists() and dest.stat().st_size > 1024:
        with dest.open("rb") as stream:
            return "cached" if stream.read(4) == b"%PDF" else "bad:cached-not-pdf"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read()
    except (urllib.error.URLError, OSError) as e:
        return f"error:{e}"
    if not body.startswith(b"%PDF"):
        head = bytes(body[:80]).decode("utf-8", "replace").strip()
        return f"bad:not-pdf({head[:40]!r})"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return "ok"


def extract_text(pdf: Path, txt: Path) -> str:
    """Extract PDF text. Returns 'cached' | 'ok' | 'error:<msg>'."""
    if txt.exists() and txt.stat().st_size > 200:
        return "cached"
    txt.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("pdftotext"):
        proc = subprocess.run(
            ["pdftotext", "-q", "-enc", "UTF-8", str(pdf), str(txt)],
            capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and txt.exists() and txt.stat().st_size > 200:
            return "ok"
        txt.unlink(missing_ok=True)
    try:
        import fitz  # PyMuPDF fallback
        with fitz.open(pdf) as doc:
            text = "\n".join(page.get_text() for page in doc)
        if len(text) > 200:
            txt.write_text(text, encoding="utf-8")
            return "ok"
        return "error:no-text-extracted"
    except ImportError:
        return "error:pdftotext-missing-and-no-pymupdf"


def split_into_passages(text: str, max_chars: int = 500):
    """Passage splitting, mirroring ingest.split_into_passages."""
    paragraphs = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(paragraphs) < 3:
        paragraphs = [b.strip() for b in text.split("\n")
                      if b.strip() and len(b.strip()) > 3]
    passages = []
    current = ""
    for para in paragraphs:
        if len(para) > max_chars:
            if current and len(current) > 10:
                passages.append(current)
            current = ""
            chunk = ""
            for sent in para.replace("\n", " ").split(". "):
                if len(chunk) + len(sent) > max_chars and chunk:
                    passages.append(chunk.strip())
                    chunk = ""
                chunk += sent + ". "
            if chunk.strip():
                passages.append(chunk.strip())
        elif len(current) + len(para) > max_chars:
            if current:
                passages.append(current)
            current = para
        else:
            current = current + "\n" + para if current else para
    if current and len(current) > 10:
        passages.append(current)
    return [p for p in passages if len(p.strip()) > 30]


def build_corpus(entries) -> tuple:
    """Index all extracted texts into passage records. Returns (corpus, failures)."""
    corpus, failures = [], []
    for entry in entries:
        txt = txt_path(entry["url"])
        if not txt.exists():
            failures.append({"key": entry["key"], "reason": "not-extracted"})
            continue
        text = txt.read_text(encoding="utf-8")
        key = entry["key"]
        date = key.split("_", 1)[0]
        lang = key.rsplit("_", 1)[-1]
        # Page markers (\f) carry provenance: keep the page number on records.
        pages = text.split("\f") if "\f" in text else [text]
        n = 0
        for page_no, page in enumerate(pages):
            for passage in split_into_passages(page):
                corpus.append({
                    "id": f"{key}_p{page_no + 1:02d}_{n:03d}",
                    "doc_id": key,
                    "lang": lang,
                    "page": page_no + 1,
                    "text": passage,
                    "booklet_date": date,
                    "source_file": f"{key}.pdf",
                    "booklet_url": entry["url"],
                })
                n += 1
    return corpus, failures


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch + extract + index booklet PDFs")
    ap.add_argument("--list", action="store_true",
                    help="print the download plan and cache state, do nothing else")
    ap.add_argument("--limit", type=int, default=0,
                    help="only process the first N booklet URLs (smoke runs)")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="do not download; re-extract/re-index the local cache")
    ap.add_argument("--out", type=Path,
                    help="separate corpus output (required for limited smoke runs)")
    args = ap.parse_args(argv)
    output = args.out or BOOKLET_CORPUS_JSON
    if args.limit < 0 or (args.limit and not args.list
                         and output.resolve() == BOOKLET_CORPUS_JSON.resolve()):
        print("ERROR: --limit must be non-negative; limited runs require a separate --out", file=sys.stderr)
        return 1

    if not DATASET_PATH.exists():
        sys.exit(f"eval dataset not found: {DATASET_PATH} (run: make eval-data)")

    entries = list_booklets(load_dataset())
    if args.limit:
        entries = entries[:args.limit]

    if args.list:
        cached = sum(1 for e in entries if pdf_path(e["url"]).exists())
        total_bytes = sum(pdf_path(e["url"]).stat().st_size
                          for e in entries if pdf_path(e["url"]).exists())
        print(f"{len(entries)} unique booklet PDFs "
              f"({cached} cached, {total_bytes / 1e6:.1f} MB on disk)")
        for e in entries:
            state = "cached" if pdf_path(e["url"]).exists() else "to-fetch"
            print(f"  [{state:8s}] {e['key']}  ({e['n_items']} items)")
        return 0

    fetch_states = {}
    if not args.skip_fetch:
        print(f"Fetching {len(entries)} booklet PDFs into {BOOKLET_PDF_DIR} ...")
        for i, entry in enumerate(entries, 1):
            state = fetch_pdf(entry["url"], pdf_path(entry["url"]))
            fetch_states[entry["key"]] = state
            if state != "cached":
                print(f"  [{i:2d}/{len(entries)}] {entry['key']}: {state}")
                time.sleep(POLITE_DELAY_S)

    extract_states = {}
    for entry in entries:
        pdf = pdf_path(entry["url"])
        if not pdf.exists():
            extract_states[entry["key"]] = "skipped(no-pdf)"
            continue
        with pdf.open("rb") as stream:
            if stream.read(4) != b"%PDF":
                extract_states[entry["key"]] = "error:not-pdf"
                continue
        extract_states[entry["key"]] = extract_text(pdf, txt_path(entry["url"]))

    ok_entries = [e for e in entries
                  if txt_path(e["url"]).exists()
                  and extract_states.get(e["key"], "cached") in ("cached", "ok")]
    corpus, failures = build_corpus(ok_entries)

    indexed_docs = {r["doc_id"] for r in corpus}
    missing = [e["key"] for e in entries if e["key"] not in indexed_docs]
    if not entries or not corpus or missing or failures:
        print("ERROR: incomplete corpus; existing output preserved", file=sys.stderr)
        print(f"Missing documents: {missing}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output_mode = output.stat().st_mode & 0o777 if output.exists() else 0o644
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=output.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(corpus, stream, ensure_ascii=False)
        temporary.chmod(output_mode)
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    by_lang = {}
    for r in corpus:
        by_lang[r["lang"]] = by_lang.get(r["lang"], 0) + 1
    print(f"\nIndexed {len(corpus)} passages from {len(ok_entries)} booklets "
          f"-> {output}")
    print(f"By language: {by_lang}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
