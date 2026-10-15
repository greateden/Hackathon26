# Swiss voting-booklet claim verification — HackApertus Track 2A

The submission project is in [track_2a/](track_2a/README.md), following the
[official Track 2A layout](https://github.com/HackApertus/project-template/tree/main/track_2a).
It checks a claim against a specified voting booklet using Apertus and cites
supporting PDF passages.

Start with the [project README](track_2a/README.md),
[running instructions](track_2a/docs/RUNNING.md) and
[submission status](track_2a/docs/PROJECT_STATUS.md).
Run `make run` here or inside `track_2a/` for the single-request development demo.
The public `linux/amd64` evaluation image is documented in the [project README](track_2a/README.md);
the batch CLI requires an externally supplied Apertus endpoint and credential.
Private-set qualification and failure-row scoring remain unverified.

The local virtual environment remains at `.venv/`. Local data, corpora and
scratch files were preserved under `track_2a/`; they are not a submission bundle.
Do not upload this working directory as a ZIP: use reviewed Git-tracked files.
