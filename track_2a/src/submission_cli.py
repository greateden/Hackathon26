"""Evaluation JSONL entry point. Source files are read-only; no label fallback."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from contextlib import redirect_stdout
from collections import OrderedDict

import booklet_app as app


def resolved_beneath(path, root, description, *, strict=True):
    """Resolve a path and reject absolute, ``..`` or symlink escapes."""
    root = Path(root).resolve(strict=True)
    resolved = Path(path).resolve(strict=strict)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{description} must remain beneath {root.name} root") from exc
    return resolved


def read_cases(path, data_root):
    data_root = Path(data_root).resolve(strict=True)
    path = resolved_beneath(path, data_root, "Input", strict=True)
    cases = []
    seen = set()
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Blank input line {number}")
            raw = app.strict_json(line)
            if not isinstance(raw, dict):
                raise ValueError(f"Line {number} must be an object")
            if not isinstance(raw.get("vote"), str) or not raw["vote"].strip():
                raise ValueError(f"Line {number} requires vote")
            if "booklet" in raw:
                source = raw["booklet"].get("path") if isinstance(raw["booklet"], dict) else None
                if not isinstance(source, str) or "://" in source:
                    raise ValueError(f"Line {number} requires a supplied local PDF")
                pdf = Path(source)
                pdf = pdf if pdf.is_absolute() else data_root / pdf
                if not pdf.is_file():
                    raise ValueError(f"Line {number}: supplied PDF does not exist")
                raw["booklet"]["path"] = str(
                    resolved_beneath(pdf, data_root, "Supplied PDF", strict=True))
            request = app.validate_request(raw, data_root)
            request["pipeline_version"] = app.CANDIDATE_PIPELINE
            if request["id"] in seen:
                raise ValueError(f"Duplicate input id at line {number}")
            seen.add(request["id"])
            cases.append(request)
    return cases


def run(input_path, output_path, data_root=None, judge_factory=None, retriever_factory=None,
        output_root=None):
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output must differ")
    root = Path(data_root) if data_root is not None else (
        Path("/data") if Path("/data").is_dir() else input_path.parent)
    root = root.resolve(strict=True)
    if output_root is None and root == Path("/data").resolve(strict=False):
        output_root = Path("/output")
    if output_root is not None:
        output_path = resolved_beneath(output_path, output_root, "Output", strict=False)
    cases = read_cases(input_path, root)
    if any(request.get("booklet") == str(output_path.resolve()) for request in cases):
        raise ValueError("Output must not overwrite a supplied PDF")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    judge_factory = judge_factory or app.SubmissionJudge
    retriever_factory = retriever_factory or app.BookletRetriever
    failures = 0
    retriever = None
    booklets = OrderedDict()
    # One judge per batch; official per-case inference metrics remain unchanged.
    judge = judge_factory() if cases else None
    with output_path.open("w", encoding="utf-8") as out:
        for request in cases:
            case_started = time.perf_counter()
            try:
                if request["task"] == "advanced" and retriever is None:
                    retriever = retriever_factory()
                with redirect_stdout(sys.stderr):
                    booklet = None
                    if request["task"] == "advanced":
                        pdf = Path(request["booklet"])
                        stat = pdf.stat()
                        key = (str(pdf), request.get("booklet_language"), stat.st_size, stat.st_mtime_ns)
                        if key not in booklets:
                            booklets[key] = app.load_booklet(str(pdf), request.get("booklet_language"))
                            if len(booklets) > 8:
                                booklets.popitem(last=False)
                        booklets.move_to_end(key)
                        booklet = booklets[key]
                    result = app.classify(request, judge, retriever=retriever, booklet=booklet)
                response = app.submission_output(result)
                if response["label"] != 1 and request["task"] == "advanced":
                    if not response["evidence"]:
                        raise ValueError("Missing document evidence")
                    for item in response["evidence"]:
                        if type(item["page"]) is not int or item["page"] < 1 or len(item["text"]) > 5000:
                            raise ValueError("Invalid document evidence")
                out.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + "\n")
                out.flush()
                app.profile_log("case", case_id=request["id"],
                                duration_s=f"{time.perf_counter() - case_started:.3f}")
            except Exception as exc:
                failures += 1
                # An explicit error row preserves ID accounting, not an invented prediction.
                out.write(json.dumps({"id": request["id"], "label": None,
                                      "error": "classification_failed:" + type(exc).__name__},
                                     ensure_ascii=False, allow_nan=False) + "\n")
                out.flush()
                print(f"Case {request['id']}: {type(exc).__name__}; error row written", file=sys.stderr)
                app.profile_log("case", case_id=request["id"],
                                duration_s=f"{time.perf_counter() - case_started:.3f}",
                                status="error")
    if failures:
        print(f"{failures}/{len(cases)} cases failed; successful cases retained", file=sys.stderr)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", "--out", dest="output", required=True, type=Path)
    args = parser.parse_args()
    # Evaluation variables take precedence over development aliases.
    if "BASE_URL" in os.environ:
        os.environ["LLM_BASE_URL"] = os.environ["BASE_URL"]
    if "API_KEY" in os.environ:
        os.environ["LLM_API_KEY"] = os.environ["API_KEY"]
    os.environ.setdefault("LLM_NAME", "swiss-ai/Apertus-v1.5-70B")
    os.environ.setdefault("LLM_TOKEN_PREFLIGHT", "optional")
    os.environ["SUBMISSION_MODEL_REQUIRED"] = "1"
    try:
        return run(args.input, args.output)
    except Exception as exc:
        print(f"Prediction batch failed: {type(exc).__name__}; check input and endpoint configuration", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
