"""Corpus publication safeguards; no network, PDFs or cached models required."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import fetch_booklets as ingestion


class IngestionSafetyTests(unittest.TestCase):
    def test_corrupt_cached_pdf_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "cached.pdf"
            original = b"<html>" + b"x" * 2048
            pdf.write_bytes(original)
            with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
                self.assertEqual(ingestion.fetch_pdf("https://example.invalid/a.pdf", pdf),
                                 "bad:cached-not-pdf")
            self.assertEqual(pdf.read_bytes(), original)

    def test_valid_cached_pdf_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "cached.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * 2048)
            with patch("urllib.request.urlopen", side_effect=AssertionError("network")):
                self.assertEqual(ingestion.fetch_pdf("https://example.invalid/a.pdf", pdf), "cached")

    def test_empty_or_missing_inputs_preserve_existing_corpus(self):
        for rows in ([], [{"booklet_url": "https://example.invalid/a.pdf", "reference_language": "de"}]):
            with self.subTest(rows=len(rows)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                data = root / "dataset.jsonl"
                data.write_text("".join(json.dumps(row) + "\n" for row in rows))
                corpus = root / "corpus.json"
                original = b'[{"preserved": true}]\n'
                corpus.write_bytes(original)
                with patch.object(ingestion, "DATASET_PATH", data), \
                     patch.object(ingestion, "load_dataset", return_value=rows), \
                     patch.object(ingestion, "BOOKLET_PDF_DIR", root / "pdf"), \
                     patch.object(ingestion, "BOOKLET_TEXT_DIR", root / "text"), \
                     patch.object(ingestion, "BOOKLET_CORPUS_JSON", corpus):
                    self.assertEqual(ingestion.main(["--skip-fetch"]), 1)
                self.assertEqual(corpus.read_bytes(), original)

    def test_limited_run_cannot_publish_to_canonical_corpus(self):
        with patch.object(ingestion, "load_dataset", side_effect=AssertionError("must fail before ingestion")):
            self.assertEqual(ingestion.main(["--limit", "1"]), 1)

    def test_complete_subset_can_publish_to_separate_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.jsonl"
            data.write_text("fixture")
            canonical, out = root / "corpus.json", root / "subset.json"
            canonical.write_text("preserved")
            out.write_text("previous subset")
            out.chmod(0o640)
            rows = [{"booklet_url": "https://example.invalid/a.pdf", "reference_language": "de"}]
            entry = ingestion.list_booklets(rows)[0]
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF" + b"x" * 2048)
            txt = root / "source.txt"
            txt.write_text("A complete source paragraph with sufficient text for a passage. " * 5)
            with patch.object(ingestion, "DATASET_PATH", data), \
                 patch.object(ingestion, "load_dataset", return_value=rows), \
                 patch.object(ingestion, "BOOKLET_CORPUS_JSON", canonical), \
                 patch.object(ingestion, "pdf_path", return_value=pdf), \
                 patch.object(ingestion, "txt_path", return_value=txt):
                self.assertEqual(ingestion.main(["--skip-fetch", "--limit", "1", "--out", str(out)]), 0)
            self.assertEqual(canonical.read_text(), "preserved")
            self.assertEqual(out.stat().st_mode & 0o777, 0o640)
            self.assertEqual({p["doc_id"] for p in json.loads(out.read_text())}, {entry["key"]})
