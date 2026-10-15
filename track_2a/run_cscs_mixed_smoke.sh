#!/bin/sh
# Operator-run only: two paid CSCS calls (one Task A, one Task B). Not a benchmark.
set -eu

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 TRUSTED_LOCAL_PDF 'EXACT VOTE TITLE' 'CLAIM ABOUT THAT VOTE'" >&2
    exit 2
fi

pdf_path=$1
vote_text=$2
claim_text=$3
env_file=${CSCS_ENV_FILE:-"$HOME/.config/hackapertus/cscs.env"}
image_name=${CSCS_SMOKE_IMAGE:-votelens:evaluation-20261015}
smoke_platform=${CSCS_SMOKE_PLATFORM:-linux/amd64}
case "$smoke_platform" in
    linux/amd64|linux/arm64) ;;
    *) echo "ERROR: CSCS_SMOKE_PLATFORM must be linux/amd64 or linux/arm64" >&2; exit 2 ;;
esac

test -f "$pdf_path" || { echo "ERROR: trusted local PDF not found" >&2; exit 2; }
test -f "$env_file" || { echo "ERROR: CSCS env file not found: $env_file" >&2; exit 2; }

# The provisioned file is trusted operator configuration. Never print it or enable xtrace.
set -a
# shellcheck disable=SC1090
. "$env_file"
set +a
test -n "${CSCS_INFERENCE_API_KEY:-}" || {
    echo "ERROR: CSCS_INFERENCE_API_KEY is missing from the env file" >&2
    exit 2
}
BASE_URL=https://api.inference.cscs.ch/v1
API_KEY=$CSCS_INFERENCE_API_KEY
export BASE_URL API_KEY

share_root=${CSCS_SMOKE_TMPDIR:-"$PWD/.cscs-mixed-smoke"}
mkdir -p "$share_root"
work_dir=$(mktemp -d "$share_root/votelens-cscs.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM
mkdir "$work_dir/data" "$work_dir/output"
chmod 777 "$work_dir/output"
cp "$pdf_path" "$work_dir/data/booklet.pdf"
thread_env="$work_dir/thread.env"
: > "$thread_env"
for variable in OMP_NUM_THREADS MKL_NUM_THREADS OPENBLAS_NUM_THREADS VOTELENS_PROFILE; do
    case "$variable" in
        OMP_NUM_THREADS) value=${OMP_NUM_THREADS:-} ;;
        MKL_NUM_THREADS) value=${MKL_NUM_THREADS:-} ;;
        OPENBLAS_NUM_THREADS) value=${OPENBLAS_NUM_THREADS:-} ;;
        VOTELENS_PROFILE) value=${VOTELENS_PROFILE:-} ;;
    esac
    if [ -n "$value" ]; then
        printf '%s=%s\n' "$variable" "$value" >> "$thread_env"
    fi
done

python3 - "$work_dir/data/cases.jsonl" "$vote_text" "$claim_text" <<'PY'
import json
import sys

destination, vote, claim = sys.argv[1:]
rows = [
    {"id": "cscs-task-a", "vote": vote,
     "booklet": {"path": "booklet.pdf"},
     "claim": {"text": claim}},
    {"id": "cscs-task-b", "vote": "Referenzprüfung",
     "reference": {"text": "Der Bundesrat empfiehlt, die Vorlage abzulehnen.",
                   "language": "de"},
     "claim": {"text": "Der Bundesrat empfiehlt, die Vorlage abzulehnen.",
               "language": "de"}},
]
with open(destination, "w", encoding="utf-8") as stream:
    for row in rows:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
PY

echo "LIVE CSCS SMOKE: exactly two authorised inference requests; this is not a benchmark."
echo "docker run --rm --platform $smoke_platform -e BASE_URL=<redacted> -e API_KEY=<redacted> --env-file <thread-settings> -v <input>:/data:ro -v <output>:/output $image_name --input /data/cases.jsonl --output /output/predictions.jsonl"
set +e
docker run --rm --platform "$smoke_platform" \
    -e BASE_URL -e API_KEY \
    --env-file "$thread_env" \
    -v "$work_dir/data:/data:ro" -v "$work_dir/output:/output" \
    "$image_name" --input /data/cases.jsonl --output /output/predictions.jsonl
docker_exit=$?
set -e
echo "docker_exit=$docker_exit"

predictions="$work_dir/output/predictions.jsonl"
validation_exit=1
if [ -f "$predictions" ]; then
    set +e
    python3 - "$predictions" <<'PY'
import json
import sys

expected = {"cscs-task-a", "cscs-task-b"}
label_names = {0: "entailment", 1: "neutral", 2: "contradiction"}
with open(sys.argv[1], encoding="utf-8") as stream:
    rows = [json.loads(line) for line in stream if line.strip()]
if {row.get("id") for row in rows} != expected or len(rows) != 2:
    raise SystemExit("SCHEMA FAIL: expected exactly the two requested IDs")
for row in rows:
    if set(row) != {"id", "label", "label_name", "evidence", "metrics"}:
        raise SystemExit(f"SCHEMA FAIL {row.get('id')}: unexpected fields or error row")
    label = row["label"]
    if type(label) is not int or label not in label_names or row["label_name"] != label_names[label]:
        raise SystemExit(f"SCHEMA FAIL {row['id']}: invalid label")
    if not isinstance(row["evidence"], list):
        raise SystemExit(f"SCHEMA FAIL {row['id']}: evidence is not a list")
    for item in row["evidence"]:
        if set(item) != {"page", "text"} or not isinstance(item["text"], str) or not item["text"]:
            raise SystemExit(f"SCHEMA FAIL {row['id']}: invalid evidence item")
        if item["page"] is not None and (type(item["page"]) is not int or item["page"] < 1):
            raise SystemExit(f"SCHEMA FAIL {row['id']}: invalid citation page")
    metrics = row["metrics"]
    if set(metrics) != {"input_tokens", "output_tokens", "inference_time_ms"}:
        raise SystemExit(f"SCHEMA FAIL {row['id']}: invalid metrics fields")
    if (type(metrics["input_tokens"]) is not int or metrics["input_tokens"] < 1 or
            type(metrics["output_tokens"]) is not int or metrics["output_tokens"] < 1 or
            type(metrics["inference_time_ms"]) is not int or metrics["inference_time_ms"] < 0):
        raise SystemExit(f"SCHEMA FAIL {row['id']}: invalid token/latency values")
    print(json.dumps({"id": row["id"], "label": label,
                      "label_name": row["label_name"],
                      "citation_pages": [item["page"] for item in row["evidence"]],
                      **metrics}, ensure_ascii=False))
print("schema_validation=PASS (two-case smoke only; no accuracy claim)")
PY
    validation_exit=$?
    set -e
else
    echo "SCHEMA FAIL: predictions.jsonl was not created" >&2
fi
echo "validation_exit=$validation_exit"

record_dir=${CSCS_SMOKE_RECORD_DIR:-"$PWD/data/experiments/cscs-mixed-smoke-$(date -u +%Y%m%dT%H%M%SZ)"}
mkdir -p "$record_dir"
if [ -f "$predictions" ]; then
    cp "$predictions" "$record_dir/predictions.jsonl"
fi
printf '{"docker_exit":%s,"validation_exit":%s,"requests":2,"benchmark":false}\n' \
    "$docker_exit" "$validation_exit" > "$record_dir/run.json"
echo "record_dir=$record_dir"

if [ "$docker_exit" -ne 0 ] || [ "$validation_exit" -ne 0 ]; then
    exit 1
fi
