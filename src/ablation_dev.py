"""Ablation runner for judge prompt/judging configs on the FIXED dev split.

Runs eval_nli.py as a subprocess per (prompt-config x evidence-mode) combo so
each run keeps writing its own result JSON (never overwrites another run),
then prints a comparison table (accuracy, macro-F1, per-class F1, error
counts, latency) and writes one combined ablation JSON; repeated t0 runs are
compared item-by-item to detect nondeterministic decoding.

This script runs NO model itself: every label comes from eval_nli.py against
the endpoint configured via OPENAI_BASE_URL (or the lexical fallback if you
explicitly choose --backend lexical for plumbing only - those numbers must
never be quoted as model quality, see AGENTS.md).

Memory procedure (hard rule, 2026-10-10): before starting the model server,
unload other memory-heavy apps (MTPLX etc.). Start the server in another
terminal BEFORE the run, e.g.
    make serve-apertus
stop it immediately after (Ctrl-C in its terminal), and verify the port is
free:  lsof -nP -iTCP:8080 -sTCP:LISTEN
The runner checks the endpoint up front and refuses to start without it
(--dry-run skips the check); no silent lexical fallback here either.

Usage (from src/):
    python3 ablation_dev.py --dry-run
    python3 ablation_dev.py --backend openai --limit 5      # plumbing check
    python3 ablation_dev.py --backend openai                 # full 60-item ablation
    python3 ablation_dev.py --configs strict --evidence oracle --limit 10

Factorial arms (2026-10-10): `fill_only` (fill style, no window) and
`window_only` (drop style, window on) each isolate ONE factor of `select`.
Run `python3 diag_evidence_ablation.py` offline FIRST: it verifies which
cells are byte-identical twins of recorded runs (retrieve mode never
exercises the window; oracle evidence is a single sub-cap chunk, so style
is inert there), so redundant cells are skipped rather than re-run for
presentation. Pair NEW cells with same-session t0 controls, e.g.
    python3 ablation_dev.py --backend openai --configs t0,window_only --evidence oracle --repeats 2 --repeat-configs t0
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, OPENAI_BASE_URL, JUDGE_MODEL
from nli_judge import PROMPT_CONFIGS

DEFAULT_CONFIGS = ["t0", "strict", "select"]
DEFAULT_EVIDENCE = ["retrieve-v2", "oracle"]
CLASSES = ["entailment", "neutral", "contradiction"]


def endpoint_ok(base_url, timeout=5):
    """Prefer urllib (stdlib, works in slim containers); else requests."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{base_url}/v1/models",
                                    timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def run_combo(prompt_config, evidence, backend, limit):
    """Invoke eval_nli.py once; return (list of (path, payload), ok-flag)."""
    here = Path(__file__).resolve().parent
    runs = []
    cmd = [sys.executable, str(here / "eval_nli.py"),
           "--split", "dev", "--backend", backend,
           "--evidence", evidence, "--prompt-config", prompt_config]
    if limit:
        cmd += ["--limit", str(limit)]
    print(f"\n=== RUN {prompt_config}/{evidence} "
          f"(n={limit or 'full dev'}) ===", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=here)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        print(f"!!! RUN FAILED (exit {proc.returncode}) - aborting the "
              "ablation so partial sets are never compared", flush=True)
        return runs, False
    newest = max(DATA_DIR.glob("eval_results_*.json"),
                 key=lambda p: p.stat().st_mtime)
    payload = json.loads(newest.read_text(encoding="utf-8"))
    runs.append((newest, payload))
    print(f"--- done in {elapsed:.0f}s -> {newest.name}", flush=True)
    return runs, True


def labels_of(payload):
    return [it.get("pred") for it in payload["items"]]


def compare_table(all_runs):
    lines = []
    header = (f"{'config':<10} {'evidence':<13} {'rep':<4} {'n':>4} "
              f"{'acc':>6} {'macroF1':>8} " +
              " ".join(f"{c[:4]:>7}" for c in CLASSES) +
              f" {'errs':>5} {'medLat_s':>9}")
    lines.append(header)
    for r in all_runs:
        s = r["summary"]
        pc = s["per_class"]
        lines.append(
            f"{r['config']:<10} {r['evidence']:<13} {r['rep']:<4} "
            f"{s['n']:>4} {s['accuracy']:>6} {s['macro_f1']:>8} " +
            " ".join(f"{pc[c]['f1']:>7}" for c in CLASSES) +
            f" {s['errors']:>5} "
            f"{str(s['median_latency_s']):>9}")
    return "\n".join(lines)


def determinism_checks(all_runs):
    """Same config+evidence run twice at T=0 -> labels must match itemwise."""
    out = []
    by_key = {}
    for r in all_runs:
        by_key.setdefault((r["config"], r["evidence"]), []).append(r)
    for (cfg, ev), group in by_key.items():
        if len(group) < 2:
            continue
        a, b = group[0]["labels"], group[1]["labels"]
        same = sum(1 for x, y in zip(a, b) if x == y)
        out.append({"config": cfg, "evidence": ev,
                    "identical_predictions": same, "n": len(a),
                    "agree_rate": round(same / max(1, len(a)), 3)})
    return out
def main():
    ap = argparse.ArgumentParser(description="dev-split prompt ablation")
    ap.add_argument("--configs", default=",".join(DEFAULT_CONFIGS),
                    help="comma list from " + ",".join(sorted(PROMPT_CONFIGS)))
    ap.add_argument("--evidence", default=",".join(DEFAULT_EVIDENCE),
                    help="comma list: oracle,retrieve,retrieve-v2")
    ap.add_argument("--backend", default="openai",
                    choices=["lexical", "mlx", "ollama", "openai"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=1,
                    help="runs per combo (>=2 enables the determinism check "
                         "for repeated configs)")
    ap.add_argument("--repeat-configs", default="t0",
                    help="configs to run --repeats times (determinism probe)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    for c in configs:
        if c not in PROMPT_CONFIGS:
            sys.exit(f"unknown prompt config {c!r}; "
                     f"valid: {sorted(PROMPT_CONFIGS)}")
    evidences = [e.strip() for e in args.evidence.split(",") if e.strip()]

    rep_cfgs = [c.strip() for c in args.repeat_configs.split(",")]
    plan = []
    for ev in evidences:
        for cfg in configs:
            reps = args.repeats if cfg in rep_cfgs else 1
            for rep in range(max(1, reps)):
                plan.append((cfg, ev, rep + 1))

    print("Ablation plan (fixed seeded dev split, separate JSON per run):")
    for cfg, ev, rep in plan:
        print(f"  {cfg}/{ev} rep{rep}")
    print(f"total runs: {len(plan)} x {args.limit or 60} items")
    if args.dry_run:
        return

    if args.backend in ("openai", "ollama"):
        if not endpoint_ok(OPENAI_BASE_URL):
            sys.exit(f"ERROR: no OpenAI-compatible endpoint at "
                     f"{OPENAI_BASE_URL}. Start the model server first "
                     "(make serve-apertus in another terminal), with other "
                     "memory-heavy apps UNLOADED. Refusing to run "
                     "lexically as a stand-in for a model.")

    all_runs = []
    ok = True
    t_total = time.perf_counter()
    for cfg, ev, rep in plan:
        runs, ok = run_combo(cfg, ev, args.backend, args.limit)
        if not ok:
            break
        for path, payload in runs:
            all_runs.append({"config": cfg, "evidence": ev, "rep": rep,
                             "file": str(path),
                             "summary": payload["summary"],
                             "labels": labels_of(payload)})
    if not all_runs:
        sys.exit("no successful runs")

    print("\n" + compare_table(all_runs))
    det = determinism_checks(all_runs)
    if det:
        print("\nDeterminism (repeated T=0 runs must agree itemwise):")
        for d in det:
            flag = ("OK" if d["agree_rate"] == 1.0 else
                    "NONDETERMINISTIC - server may be ignoring "
                    "temperature=0; treat single-run deltas as noise")
            print(f"  {d['config']}/{d['evidence']}: "
                  f"{d['identical_predictions']}/{d['n']} identical "
                  f"[{flag}]")
    out = DATA_DIR / (f"ablation_{datetime.now():%Y%m%d_%H%M%S}"
                      f"_{args.backend}.json")
    out.write_text(json.dumps({
        "meta": {
            "created_utc": datetime.now(timezone.utc)
                           .isoformat(timespec="seconds"),
            "backend": args.backend,
            "model": JUDGE_MODEL if args.backend == "openai" else None,
            "endpoint": OPENAI_BASE_URL if args.backend == "openai" else None,
            "split": "dev", "n_items": args.limit or 60,
            "note": ("paired comparison vs t0; single runs per combo unless "
                     "repeats were requested; do not quote without the "
                     "paired baseline"),
        },
        "runs": [{"config": r["config"], "evidence": r["evidence"],
                  "rep": r["rep"], "file": r["file"],
                  "summary": r["summary"]} for r in all_runs],
        "determinism": det,
        "total_s": round(time.perf_counter() - t_total, 1),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nablation JSON: {out}")
    print("DONE. Stop the model server now if nothing else needs it "
          "(Ctrl-C in its terminal); verify: lsof -nP -iTCP:8080 "
          "-sTCP:LISTEN")


if __name__ == "__main__":
    main()
