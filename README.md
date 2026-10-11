# Swiss voting-booklet claim verification — HackApertus Track 2A

The submission project is in [track_2a/](track_2a/README.md), following the
[official Track 2A layout](https://github.com/HackApertus/project-template/tree/main/track_2a).
It checks a claim against a specified voting booklet using Apertus and cites
supporting PDF passages.

Start with the [project README](track_2a/README.md),
[running instructions](track_2a/docs/RUNNING.md) and
[submission status](track_2a/docs/PROJECT_STATUS.md).
Run `make run` here or inside `track_2a/`; both launch the Docker application.
A separately provisioned model endpoint is still required: self-contained
model startup and clean-checkout Docker execution remain unverified.

The local virtual environment remains at `.venv/`. Local data, corpora and
scratch files were preserved under `track_2a/`; they are not a submission bundle.
Do not upload this working directory as a ZIP: use reviewed Git-tracked files.
