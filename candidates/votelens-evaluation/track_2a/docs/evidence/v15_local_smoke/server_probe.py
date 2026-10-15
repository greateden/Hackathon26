"""Observational wrapper: records the real loader and unchanged tokeniser output."""
import hashlib
import json
import os
from pathlib import Path
import mlx_lm.server as server
from huggingface_hub import snapshot_download
OUT = Path(__file__).parent
original_load = server.ModelProvider._load
original_tokenize = server.ResponseGenerator._tokenize

def observed_load(self, model_path, *args, **kwargs):
    result = original_load(self, model_path, *args, **kwargs)
    snapshot = Path(snapshot_download(model_path, local_files_only=True))
    record = {'pid': os.getpid(), 'model_key': self.model_key,
              'snapshot': str(snapshot), 'revision': snapshot.name,
              'model_class': type(self.model).__module__ + '.' + type(self.model).__name__,
              'config': json.loads((snapshot / 'config.json').read_text()),
              'shards': [{'file': f.name, 'bytes': f.stat().st_size, 'blob': str(f.resolve())}
                         for f in sorted(snapshot.glob('*.safetensors'))]}
    (OUT / 'loaded_model.json').write_text(json.dumps(record, indent=2))
    print('ACTUALLY_LOADED', json.dumps(record), flush=True)
    return result

def observed_tokenize(self, tokenizer, request, args):
    result = original_tokenize(self, tokenizer, request, args)
    prompt, segments, types, state = result
    record = {'prompt_tokens': len(prompt), 'token_ids': prompt,
              'segment_lengths': [len(s) for s in segments], 'initial_state': state,
              'messages': request.messages, 'model_key': self.model_provider.model_key}
    (OUT / 'server_prompt.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print('ACTUAL_PROMPT_TOKENS', len(prompt), flush=True)
    return result

server.ModelProvider._load = observed_load
server.ResponseGenerator._tokenize = observed_tokenize
server.main()
