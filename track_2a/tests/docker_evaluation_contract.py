"""Offline amd64 integration fixture; mock completions are not quality evidence.

Prepare on host: python3 tests/docker_evaluation_contract.py --prepare DIRECTORY
Run in image with /data read-only, /output writable and --network none.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    text = b"BT /F1 12 Tf 30 100 Td (La reforme est acceptee.) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(text)).encode() + b" >>\nstream\n" + text + b"\nendstream"]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    (root / "fixture.pdf").write_bytes(pdf)
    common = {"vote": "Réforme", "claim": {"text": "Die Reform wird angenommen.", "language": "de"}}
    rows = [dict(common, id="A", booklet={"path": "fixture.pdf", "language": "fr"}),
            dict(common, id="B", reference={"text": "La riforma è accettata.", "language": "it"})]
    (root / "cases.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def verify():
    assert os.getuid() != 0
    try:
        Path("/data/must-not-write").write_text("invalid")
    except OSError:
        pass
    else:
        raise AssertionError("/data is writable")
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            assert self.headers["Authorization"] == "Bearer fixture-only"
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(request)
            assert "Réforme" in request["messages"][1]["content"]
            parsed = {"label": "entailment", "reasoning": "Fixture response"}
            if "No separate proposal identity" not in request["messages"][0]["content"]:
                parsed.update(vote_status="recognised", vote_reference={"passage_id": "e1"},
                              evidence_status="sufficient", evidence_refs=[{"passage_id": "e1"}])
            body = json.dumps({"model": request["model"], "choices": [{"message": {"content": json.dumps(parsed)},
                              "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                                                                    "total_tokens": 120}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = dict(os.environ, BASE_URL=f"http://127.0.0.1:{server.server_port}/v1", API_KEY="fixture-only")
    try:
        subprocess.run([sys.executable, "/app/src/submission_cli.py", "--input", "/data/cases.jsonl",
                        "--output", "/output/predictions.jsonl"], env=env, check=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    rows = [json.loads(line) for line in Path("/output/predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in rows] == ["A", "B"]
    assert len(calls) == 2
    assert rows[0]["evidence"] == [{"page": 1, "text": "La reforme est acceptee."}]
    assert rows[1]["evidence"] == []
    for row in rows:
        assert row["label"] == 0
        assert row["metrics"]["input_tokens"] == 100
        assert row["metrics"]["output_tokens"] == 20
        assert row["metrics"]["inference_time_ms"] >= 0
    print("PASS: amd64 CPU offline encoder, mixed A/B, non-root, read-only data, UTF-8, page 1, citations and metrics")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--prepare":
        prepare(Path(sys.argv[2]))
    else:
        verify()
