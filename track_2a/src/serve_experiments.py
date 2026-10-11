"""Manual, cached-only MLX development server with token and loader provenance.

This adapter targets mlx-lm 0.32.0. It is not the Docker submission server.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

from booklet_app import MLX_MODEL

REVISION = "9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e"


def snapshot_info(model=MLX_MODEL, revision=REVISION):
    from huggingface_hub import snapshot_download
    snapshot = Path(snapshot_download(model, revision=revision, local_files_only=True))
    config = json.loads((snapshot / "config.json").read_text())
    index = json.loads((snapshot / "model.safetensors.index.json").read_text())
    shards = sorted(set(index["weight_map"].values()))
    if not shards or any(not (snapshot / name).is_file() for name in shards):
        raise ValueError("Incomplete cached MLX checkpoint; no download attempted")
    if config.get("model_type") != "apertus" or config.get("base_model") != "swiss-ai/Apertus-v1.5-8B":
        raise ValueError("Cached checkpoint is not the expected Apertus v1.5 conversion")
    metadata = {"model": model, "revision": revision, "backend": "native-mlx",
                "mlx_lm_version": importlib.metadata.version("mlx-lm"),
                "config_sha256": hashlib.sha256((snapshot / "config.json").read_bytes()).hexdigest(),
                "model_type": config["model_type"], "base_model": config["base_model"],
                "quantisation": config.get("quantization"),
                "architecture_context_tokens": config["max_position_embeddings"],
                "shards": [{"name": name, "bytes": (snapshot / name).stat().st_size,
                            "cache_blob": (snapshot / name).resolve().name} for name in shards]}
    if metadata["mlx_lm_version"] != "0.32.0":
        raise ValueError("This server adapter requires mlx-lm 0.32.0")
    return snapshot, metadata


def install_adapter(server, snapshot, metadata, context):
    """Expose metadata only after the real loader has returned successfully."""
    original_load = server.ModelProvider._load
    original_get = server.APIHandler.do_GET
    original_post = server.APIHandler.do_POST
    state = dict(metadata, loaded=False, context_tokens=context,
                 instance_id=uuid.uuid4().hex, chat_template_kwargs={"enable_thinking": False})

    def loaded(provider, model_path, adapter_path=None, draft_model_path=None):
        if model_path != MLX_MODEL or adapter_path is not None or draft_model_path is not None:
            raise ValueError("This experiment server serves only the pinned v1.5 checkpoint")
        original_load(provider, str(snapshot), None, None)
        provider.model_key = (MLX_MODEL, None, None)
        state.update(loaded=True, model_class=type(provider.model).__module__ + "." + type(provider.model).__name__)

    def send(handler, payload, status=200):
        handler._set_completion_headers(status)
        handler.end_headers()
        handler.wfile.write(json.dumps(payload).encode())

    def get(handler):
        if handler.path == "/experiment-metadata":
            send(handler, state, 200 if state["loaded"] else 503)
        elif handler.path == "/v1/models":
            send(handler, {"data": [{"id": MLX_MODEL}] if state["loaded"] else []})
        else:
            original_get(handler)

    def post(handler):
        if handler.path != "/tokenize":
            return original_post(handler)
        try:
            if not state["loaded"]:
                return send(handler, {"error": "model_not_loaded"}, 503)
            length = int(handler.headers.get("Content-Length", 0))
            if not 0 < length <= 8_000_000:
                return send(handler, {"error": "invalid_payload_size"}, 400)
            data = json.loads(handler.rfile.read(length))
            if data["model"] != MLX_MODEL:
                return send(handler, {"error": "model_mismatch"}, 400)
            request = SimpleNamespace(request_type="chat", messages=data["messages"], tools=None, role_mapping=None)
            args = SimpleNamespace(chat_template_kwargs={"enable_thinking": False})
            generator = handler.response_generator
            tokens = generator._tokenize(generator.model_provider.tokenizer, request, args)[0]
            send(handler, {"count": len(tokens), "max_model_len": context})
        except Exception as exc:
            send(handler, {"error": type(exc).__name__}, 400)

    server.ModelProvider._load = loaded
    server.APIHandler.do_GET = get
    server.APIHandler.do_POST = post


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--context", type=int, default=32768)
    args = ap.parse_args()
    if not 1 <= args.port <= 65535 or not 512 < args.context <= 262144:
        ap.error("invalid port or context limit")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    snapshot, metadata = snapshot_info()
    import mlx_lm.server as server
    install_adapter(server, snapshot, metadata, args.context)
    sys.argv = [sys.argv[0], "--model", MLX_MODEL, "--host", "127.0.0.1", "--port", str(args.port),
                "--chat-template-args", '{"enable_thinking":false}', "--prompt-cache-size", "1"]
    server.main()


if __name__ == "__main__":
    main()
