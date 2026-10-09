"""
Ingest module: load OCR text files and split them into passages for retrieval.

The only corpus source is the cleaned OCR text under
repos/VotingBooklets-mono/cleaned_ocr_txt/gemini-ocr (see config.py).
"""
from pathlib import Path
from typing import Dict, List

from config import OCR_TEXT_DIR, LANG_DIRS, YEARS


def load_ocr_text(year: str, lang: str) -> str:
    """Load a single OCR text file."""
    lang_dir = OCR_TEXT_DIR / LANG_DIRS[lang]
    # Try naming patterns
    for pattern in [f"{lang}_{year}.txt", f"{lang}{year}.txt"]:
        path = lang_dir / pattern
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def split_into_passages(text: str, max_chars: int = 500) -> List[str]:
    """
    Split document text into passages suitable for retrieval.
    
    Strategy: Split by paragraph (double newline or blank line),
    then merge very short paragraphs with neighbors,
    and split very long paragraphs at sentence boundaries.
    """
    # Split by double newline (paragraph boundaries)
    paragraphs = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            paragraphs.append(block)
    
    # If we got too few paragraphs, try single newlines
    if len(paragraphs) < 3:
        paragraphs = []
        for block in text.split("\n"):
            block = block.strip()
            if block and len(block) > 3:
                paragraphs.append(block)
    
    # Merge very short paragraphs and split very long ones
    passages = []
    current = ""
    for para in paragraphs:
        if len(para) > max_chars:
            # Flush current
            if current and len(current) > 10:
                passages.append(current)
            current = ""
            # Split long paragraph at sentence boundaries
            sentences = para.replace("\n", " ").split(". ")
            chunk = ""
            for sent in sentences:
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
    
    # Filter out very short or metadata-like passages
    passages = [p for p in passages if len(p.strip()) > 30]
    
    return passages


def load_all_documents() -> Dict[str, Dict[str, str]]:
    """
    Load all documents organized by year and language.
    
    Returns: {year: {lang: full_text}}
    """
    docs = {}
    for year in YEARS:
        docs[year] = {}
        for lang in LANG_DIRS:
            text = load_ocr_text(year, lang)
            if text:
                docs[year][lang] = text
    return docs


def build_corpus() -> List[Dict]:
    """
    Build the retrieval corpus: list of passage records.
    
    Each record: {
        "id": "de_2007_003",
        "year": "2007", 
        "lang": "de",
        "text": "...",
        "source_file": "de_2007.txt"
    }
    """
    corpus = []
    docs = load_all_documents()
    
    for year, lang_texts in docs.items():
        for lang, text in lang_texts.items():
            passages = split_into_passages(text)
            for i, passage in enumerate(passages):
                corpus.append({
                    "id": f"{lang}_{year}_{i:03d}",
                    "year": year,
                    "lang": lang,
                    "text": passage,
                    "source_file": f"{lang}_{year}.txt",
                })
    
    return corpus


if __name__ == "__main__":
    # Quick test
    corpus = build_corpus()
    print(f"Corpus built: {len(corpus)} passages")
    
    # Show stats
    from collections import Counter
    by_lang = Counter(r["lang"] for r in corpus)
    by_year = Counter(r["year"] for r in corpus)
    print(f"By language: {dict(by_lang)}")
    print(f"By year: {dict(by_year)}")
    
    # Show sample passages
    for r in corpus[:3]:
        print(f"\n--- {r['id']} ({r['lang']}) ---")
        print(r["text"][:200])