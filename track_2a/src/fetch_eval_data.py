"""Download the official Track 2A evaluation set (no 'datasets' dependency).

Fetches OSTswiss/MNLIoverSwissVotingBooklets v1.1 (public, MIT licence)
as JSONL into data/eval/ and verifies row count and label distribution.
Uses only the Python standard library.

Usage (from src/):
    python3 fetch_eval_data.py           # download unless already present
    python3 fetch_eval_data.py --force   # re-download
"""
import argparse
import json
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR

URL = ("https://huggingface.co/datasets/"
       "OSTswiss/MNLIoverSwissVotingBooklets/resolve/main/v1.1.jsonl")
OUT = DATA_DIR / "eval" / "mnli_swiss_v1.1.jsonl"
EXPECTED_ROWS = 1488
EXPECTED_REQUIRED_KEYS = {"claim", "claim_language", "reference_string",
                          "entailment_label", "reference_language"}


def download(url: str, dest: Path) -> Path:
    print(f"downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=dest.parent, delete=False) as tmp:
        with urllib.request.urlopen(url, timeout=120) as resp:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                tmp.write(chunk)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)
    return dest


def verify(path: Path) -> int:
    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("ERROR: file has no rows")
        return 1
    missing = [i for i, r in enumerate(rows)
               if not EXPECTED_REQUIRED_KEYS.issubset(r)]
    if missing:
        print(f"ERROR: {len(missing)} rows missing required keys")
        return 1
    if len(rows) != EXPECTED_ROWS:
        print(f"WARNING: expected {EXPECTED_ROWS} rows, got {len(rows)} "
              "(dataset may have changed; check before trusting results)")
    labels = Counter(r["entailment_label"] for r in rows)
    langs = Counter((r["claim_language"], r["reference_language"]) for r in rows)
    print(f"{len(rows)} rows verified")
    print(f"label distribution (0=entailment, 1=neutral, 2=contradiction): "
          f"{dict(sorted(labels.items()))}")
    print(f"claim-language distribution: "
          f"{dict(Counter(r['claim_language'] for r in rows))}")
    print(f"{sum(1 for r in rows if r['claim_language'] != r['reference_language'])} "
          f"cross-lingual claim/reference pairs across {len(langs)} language combos")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download")
    ap.add_argument("--out", default=None, help="override output path")
    args = ap.parse_args()

    dest = Path(args.out) if args.out else OUT
    if dest.exists() and not args.force:
        print(f"{dest} already exists (use --force to re-download)")
        return verify(dest)
    download(URL, dest)
    return verify(dest)


if __name__ == "__main__":
    sys.exit(main())
