#!/bin/bash
# Terminal verification only; makes two real CSCS inference calls.
set -euo pipefail
cd "$(dirname "$0")/.."
export BASE_URL="${BASE_URL:-${LLM_BASE_URL:-https://api.inference.cscs.ch/v1}}"
export API_KEY="${API_KEY:-${LLM_API_KEY:-${CSCS_INFERENCE_API_KEY:-}}}"
test -n "$API_KEY" || { echo 'Export API_KEY privately before verification.'; exit 1; }
verify_dir=$(mktemp -d "$PWD/data/evaluation-check.XXXXXX")
mkdir -p "$verify_dir/booklets" "$verify_dir/output"
# The image runs as an unprivileged user. Grant write access to this new output
# directory only; mounted input data stays read-only inside the container.
chmod a+rwx "$verify_dir/output"
curl --fail --location --max-time 120 'https://www.bk.admin.ch/dam/fr/sd-web/WeUrKyC0FyPc/2026-06-14_explications_du_conseil_federal.pdf' -o "$verify_dir/booklets/demo.pdf"
python3 - "$verify_dir" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);text='Le Conseil fédéral recommande de rejeter l’initiative pour la durabilité.'
base={'vote':'Initiative populaire « Pas de Suisse à 10 millions ! (initiative pour la durabilité) »','claim':{'text':text,'language':'fr'}}
a=dict(base,id='evaluation-A',booklet={'path':'booklets/demo.pdf','language':'fr'})
b=dict(base,id='evaluation-B',reference={'text':text,'language':'fr'})
(p/'cases.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in [a,b])+'\n',encoding='utf-8')
PY
docker build --platform linux/amd64 -t votelens:verify .
docker run --rm --platform linux/amd64 \
  -e BASE_URL -e API_KEY \
  -v "$verify_dir:/data:ro" \
  -v "$verify_dir/output:/output" \
  votelens:verify --input /data/cases.jsonl --output /output/predictions.jsonl
python3 - "$verify_dir" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);rows=[json.loads(x) for x in (p/'output/predictions.jsonl').read_text().splitlines()]
assert len(rows)==2 and {r['id'] for r in rows}=={'evaluation-A','evaluation-B'}
for r in rows:
 assert r['label'] in [0,1,2] and r['label_name']==['entailment','neutral','contradiction'][r['label']]
 assert all(type(r['metrics'][k]) is int and r['metrics'][k]>=0 for k in ['input_tokens','output_tokens','inference_time_ms'])
 if r['id']=='evaluation-A' and r['label']!=1:
  assert r['evidence'] and all(type(e['page']) is int and e['page']>=1 and len(e['text'])<=5000 for e in r['evidence'])
 print(r['id'],r['label_name'],r['metrics'])
print('Docker contract smoke passed; not an accuracy or full language benchmark.')
PY
printf 'Verification files: %s\n' "$verify_dir"
