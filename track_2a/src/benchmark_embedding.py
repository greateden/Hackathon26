"""Measure SentenceSwissBERT CPU embedding throughput without an API call.

Each thread setting runs in a fresh subprocess because PyTorch reads OpenMP
settings during import. This is opt-in and never runs as part of evaluation.
"""
import argparse
import json
import os
import platform
import subprocess
import sys


REPRESENTATIVE_TEXTS = [
    "Der Bundesrat empfiehlt, die Vorlage anzunehmen.",
    "Le Conseil fédéral recommande d'accepter le projet.",
    "Il Consiglio federale raccomanda di accettare il progetto.",
    "La Confederaziun federala propona d'acceptar il project.",
] * 8


def child(threads: str | None) -> int:
    if threads:
        os.environ["OMP_NUM_THREADS"] = threads
        os.environ["MKL_NUM_THREADS"] = threads
        os.environ["OPENBLAS_NUM_THREADS"] = threads
    import time
    import torch
    from retriever import Retriever
    from config import BATCH_SIZE, EMBEDDING_MODEL

    retriever = Retriever(device="cpu")
    for _ in range(2):
        retriever.encode(REPRESENTATIVE_TEXTS, lang_code="de_CH")
    started = time.perf_counter()
    cpu_started = time.process_time()
    repeats = 3
    for _ in range(repeats):
        retriever.encode(REPRESENTATIVE_TEXTS, lang_code="de_CH")
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu_started
    print(json.dumps({
        "platform": platform.platform(),
        "machine": platform.machine(),
        "threads_requested": threads or "default",
        "torch_intra": torch.get_num_threads(),
        "torch_inter": torch.get_num_interop_threads(),
        "batch_size": BATCH_SIZE,
        "model": EMBEDDING_MODEL,
        "texts_per_repeat": len(REPRESENTATIVE_TEXTS),
        "warmup_runs": 2,
        "measured_runs": repeats,
        "wall_s": round(wall, 3),
        "throughput_texts_per_s": round(repeats * len(REPRESENTATIVE_TEXTS) / wall, 2),
        "process_cpu_util_percent": round(100 * cpu / wall, 1),
    }))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", default="default,4,8",
                        help="comma-separated settings: default, 4 or 8")
    parser.add_argument("--_child", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._child is not None:
        return child(None if args._child == "default" else args._child)
    for setting in (item.strip() for item in args.threads.split(",")):
        if setting not in {"default", "4", "8"}:
            parser.error("--threads values must be default, 4 or 8")
        command = [sys.executable, __file__, "--_child", setting]
        env = os.environ.copy()
        if setting != "default":
            env.update({name: setting for name in
                        ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")})
        subprocess.run(command, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
