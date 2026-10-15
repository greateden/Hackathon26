"""Manually executed smoke check for the CSCS hosted Apertus v1.5 70B endpoint.

Scope: endpoint-transport verification only (endpoint reachability, served model
id, one completion, latency, usage, finish reason, parseability). A single
hand-written claim is NOT an accuracy measurement and its expected label is
reported as unvalidated plumbing information only; no evaluation metric is
produced or claimed here.

Two mutually exclusive modes:
  --dry-run  validate the configuration. No network request, no model loaded.
  --live     one GET /v1/models, then exactly ONE POST /v1/chat/completions.

Hard rules enforced by this script:
  * The API key is only ever read from the environment (CSCS_INFERENCE_API_KEY)
    and only ever placed in the Authorization header. It is never written to a
    record, printed, or copied into an error message (redact() scrubs it).
  * No lexical or other-model fallback. A missing key, an unreachable endpoint
    or a model id the endpoint does not list stops the run BEFORE the
    inference request, so no paid call is attempted.
  * No retries: the adapter is pinned to max_retries=0 and the inference step
    is a single straight-line call.
  * /tokenize is deliberately not used: it is not part of the CSCS API
    surface, so input size is read back from the completion's usage block
    (prompt_tokens) instead.
  * Nothing existing is overwritten and no evaluation result is touched: each
    invocation writes one new timestamped file.

Usage (from track_2a/, key kept outside the repository):
  python3 src/check_cscs_api.py --dry-run
  CSCS_INFERENCE_API_KEY=<key from your local secret store> \
      python3 src/check_cscs_api.py --live
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from booklet_app import build_messages
from config import DATA_DIR
from labels import LABEL_PARSE_VERSION, label_to_code
from nli_judge import parse_nli_response

SCHEMA = "hackapertus-cscs-smoke-v1"
DEFAULT_BASE_URL = "https://api.inference.cscs.ch/v1"
DEFAULT_MODEL = "swiss-ai/Apertus-v1.5-70B"
KEY_ENV = "CSCS_INFERENCE_API_KEY"
OUTPUT_DIR = DATA_DIR / "experiments" / "cscs-smoke"
# The completion is the only paid request; /v1/models is a metadata lookup.
PLANNED_CALLS = ("GET /v1/models", "POST /v1/chat/completions (exactly one)")

# One short hand-written item (German claim on a German booklet-style text).
# Its expected label is plumbing information for the parser check only.
CLAIM = "Der Bundesrat empfiehlt die Annahme der Vorlage."
EVIDENCE = ("Der Bundesrat beantragt den Stimmbürgerinnen und Stimmbürgern, "
            "die Vorlage abzulehnen.")
EXPECTED_LABEL = "contradiction"


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(value, secret):
    """Scrub the key from any string before it can reach a record or stdout.

    Defences here are layered: the key is never interpolated into a message by
    construction, and this catches the case where a library echo (a URL, a
    response body, an exception text) happens to contain it anyway.
    """
    if not isinstance(value, str):
        return value
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")


def base_and_paths(value):
    """Normalise a base URL and return (base, models_path, completions_path).

    A trailing /v1 is accepted and stripped, matching SubmissionJudge: paths
    are then built as base + '/v1/...', so both spellings work and /tokenize
    is never in the list.
    """
    url = urlparse(value)
    if url.scheme not in ("http", "https") or not url.hostname:
        raise ValueError("Endpoint must be an HTTP(S) URL with a host")
    if url.username or url.password:
        raise ValueError("Endpoint must not embed credentials")
    if url.query or url.fragment:
        raise ValueError("Endpoint must not carry a query or fragment")
    base = value.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base, base + "/v1/models", base + "/v1/chat/completions"


def resolve_output(path):
    """Return a fresh record path under data/experiments (never an existing one)."""
    path = Path(path).resolve()
    if path.suffix == ".json":
        record = path
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        record = path / f"cscs-smoke-{stamp}.json"
    root = (DATA_DIR / "experiments").resolve()
    if root not in record.parents:
        raise ValueError("Write records under track_2a/data/experiments")
    if record.exists():
        raise ValueError("Record path already exists; a new run needs a new file")
    record.parent.mkdir(parents=True, exist_ok=True)
    probe = record.parent / ".write-check"
    probe.write_text("")
    probe.unlink()
    return record


def configuration(args, secret, record):
    """Offline configuration validation. Returns issues; never touches network."""
    issues = []
    if not secret:
        issues.append(f"{KEY_ENV} is not set in the environment")
    try:
        base, models_path, completions_path = base_and_paths(args.url)
    except ValueError as exc:
        issues.append(str(exc))
        base, models_path, completions_path = args.url, "not configured", "not configured"
    if not str(args.model).strip():
        issues.append("No model id configured")
    if urlparse(args.url).scheme != "https":
        issues.append("Endpoint is not HTTPS; confirm before a live request")
    try:
        import requests  # noqa: F401
    except ImportError:
        issues.append("Python package 'requests' is unavailable")
    record.update(endpoint=base, models_path=models_path,
                  completions_path=completions_path, model=args.model,
                  key_env=KEY_ENV, api_key_present=bool(secret),
                  output_record=str(args.out),
                  planned_requests=list(PLANNED_CALLS), tokenize_calls=0,
                  token_usage_source="completion usage block", max_retries=0,
                  timeout_s=args.timeout, lexical_fallback=False,
                  inference_calls=0,
                  timeout_error="requests.exceptions.ReadTimeout "
                                "(no retry, no fallback)")
    return issues


def write_record(path, record):
    text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def models_probe(session, record, secret):
    """GET /v1/models. Returns (ok, served ids). Errors are recorded, not raised."""
    import requests
    started = time.perf_counter()
    try:
        response = session.get(record["models_path"], timeout=record["timeout_s"])
    except requests.RequestException as exc:
        record["steps"].append({
            "step": "models", "method": "GET", "path": record["models_path"],
            "status": None, "latency_s": round(time.perf_counter() - started, 3),
            "error": redact(f"{type(exc).__name__}", secret)})
        return False, []
    latency = round(time.perf_counter() - started, 3)
    step = {"step": "models", "method": "GET", "path": record["models_path"],
            "status": response.status_code, "latency_s": latency}
    try:
        served = [item["id"] for item in response.json().get("data", [])]
    except (ValueError, TypeError, AttributeError):
        served = None
        step["error"] = "models response was not a JSON model listing"
    record["steps"].append(step)
    if response.status_code // 100 != 2:
        step["error"] = f"HTTP {response.status_code} on /v1/models"
        return False, []
    return served is not None, served or []


def inference(session, record, secret):
    """Exactly one POST /v1/chat/completions. No retry, no fallback judge."""
    import requests
    messages = build_messages(CLAIM, EVIDENCE)
    payload = {"model": record["model"], "messages": messages,
               "temperature": 0, "max_tokens": record["max_tokens"], "stream": False}
    step = {"step": "completion", "method": "POST",
            "path": record["completions_path"], "status": None, "latency_s": None}
    record["steps"].append(step)
    record["inference_calls"] = 1
    started = time.perf_counter()
    try:
        response = session.post(record["completions_path"], json=payload,
                                timeout=record["timeout_s"])
    except requests.RequestException as exc:
        record["latency_s"] = round(time.perf_counter() - started, 3)
        step["latency_s"] = record["latency_s"]
        step["error"] = redact(type(exc).__name__, secret)
        record["status"] = "FAIL"
        record["error"] = redact(f"request_failed:{type(exc).__name__}", secret)
        return
    step["status"] = response.status_code
    step["latency_s"] = round(time.perf_counter() - started, 3)
    record["latency_s"] = step["latency_s"]
    if response.status_code // 100 != 2:
        record["status"] = "FAIL"
        record["error"] = redact(
            f"http_status:{response.status_code} "
            + response.text[:300].replace("\n", " "), secret)
        return
    try:
        data = response.json()
    except ValueError:
        record["status"] = "FAIL"
        record["error"] = "completion body was not JSON"
        return
    record["response_model"] = data.get("model")
    record["usage"] = data.get("usage") or {}
    choice = (data.get("choices") or [{}])[0]
    record["finish_reason"] = choice.get("finish_reason")
    raw = (choice.get("message") or {}).get("content")
    if record["response_model"] != record["model"]:
        # Identity mismatch is a failure, never a reason to try another model.
        record["status"] = "FAIL"
        record["error"] = ("response_model_mismatch_or_missing: served "
                           f"{record['response_model']!r} for {record['model']!r}")
        return
    if not isinstance(raw, str) or not raw.strip():
        record["status"] = "FAIL"
        record["error"] = "malformed_completion:no message content"
        return
    record["raw_response"] = redact(raw[:2000], secret)
    parsed = parse_nli_response(redact(raw, secret))
    record["label"] = parsed.get("label")
    record["label_code"] = label_to_code(parsed.get("label"))
    record["expected_label"] = EXPECTED_LABEL
    record["expected_label_match"] = record["label"] == EXPECTED_LABEL
    if record["label"] is None:
        record["status"] = "FAIL"
        record["error"] = "unparseable_response (recorded as an error, never as neutral)"
    elif record["finish_reason"] != "stop":
        record["status"] = "FAIL"
        record["error"] = f"incomplete_completion:{record['finish_reason']}"
    else:
        record["status"] = "PASS"

def run_live(record, secret):
    """Models listing, then at most one completion. Aborts before paying on a preflight failure."""
    import requests
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers["Authorization"] = "Bearer " + secret
    ok, served = models_probe(session, record, secret)
    if not ok:
        record["status"] = "FAIL"
        record["error"] = record["steps"][-1].get("error", "models listing failed")
        return
    record["served_models"] = served
    if record["model"] not in served:
        record["status"] = "BLOCKED"
        record["error"] = (f"{record['model']} is not listed by /v1/models; "
                           "no inference request was sent and no substitute model was used")
        return
    inference(session, record, secret)




def report(record):
    """Human summary. Credential-free by construction (no header or key text)."""
    print(f"mode={record['mode']} status={record['status']}")
    print(f"endpoint={record['endpoint']} model={record['model']}")
    print(f"api_key_present={record['api_key_present']} "
          f"(read from {record['key_env']}, never recorded)")
    for step in record["steps"]:
        line = f"  {step['method']} {step['path']} -> HTTP {step['status']} " \
               f"in {step['latency_s']}s"
        if step.get("error"):
            line += f" ({step['error']})"
        print(line)
    if record["usage"]:
        print("usage=" + json.dumps(record["usage"], sort_keys=True))
    print(f"finish_reason={record.get('finish_reason')} "
          f"label={record.get('label')} label_code={record.get('label_code')} "
          f"expected={record.get('expected_label')}")
    for line in record.get("issues", []):
        print("- " + line)
    if record.get("error"):
        print("- " + record["error"])
    print(f"record={record['record_path']}")


def parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="validate the configuration; no network request")
    mode.add_argument("--live", action="store_true",
                      help="one /v1/models lookup, then exactly one completion")
    ap.add_argument("--url", default=os.environ.get("CSCS_INFERENCE_URL", DEFAULT_BASE_URL),
                    help=f"default {DEFAULT_BASE_URL}")
    ap.add_argument("--model", default=os.environ.get("CSCS_MODEL", DEFAULT_MODEL),
                    help=f"default {DEFAULT_MODEL}")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", default=str(OUTPUT_DIR),
                    help=f"record file or directory (default {OUTPUT_DIR})")
    return ap


def main(argv=None):
    ap = parser()
    args = ap.parse_args(argv)
    if not 0 < args.timeout <= 600 or not 1 <= args.max_tokens <= 2048:
        ap.error("Invalid --timeout (0-600 s) or --max-tokens (1-2048)")
    mode = "live" if args.live else "dry-run"
    secret = os.environ.get(KEY_ENV, "")
    try:
        args.out = resolve_output(Path(args.out))
    except ValueError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    record = {"schema": SCHEMA, "mode": mode, "started_at": now(),
              "steps": [], "status": None, "max_tokens": args.max_tokens,
              "parser_version": LABEL_PARSE_VERSION, "label": None,
              "label_code": None, "usage": {}, "inference_calls": 0,
              "planned_inference_calls": 1 if mode == "live" else 0,
              "claim": CLAIM, "evidence": EVIDENCE}
    issues = configuration(args, secret, record)
    if not str(args.model).startswith("swiss-ai/Apertus-v1.5"):
        issues.append("Configured model is not an Apertus v1.5 id; "
                      "a different model would be a substitution, not a fallback")
    if mode == "live":
        if issues:
            record["status"] = "BLOCKED"
            record["error"] = "Configuration incomplete; no request was sent: " \
                              + "; ".join(issues)
        else:
            run_live(record, secret)
    else:
        record["status"] = "BLOCKED" if issues else "DRY_RUN"
    record["issues"] = issues
    record["finished_at"] = now()
    record["record_path"] = str(args.out)
    try:
        write_record(args.out, record)
    except OSError as exc:
        print(f"BLOCKED: record not written ({type(exc).__name__})", file=sys.stderr)
        return 2
    report(record)
    if record["status"] in ("DRY_RUN", "PASS"):
        return 0
    return 1 if record["status"] == "FAIL" else 2


if __name__ == "__main__":
    sys.exit(main())
