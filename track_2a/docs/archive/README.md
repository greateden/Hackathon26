# Historical research archive

These documents record earlier global-search experiments and audits. Their
measurements and caveats are retained; they do not define the current
specified-booklet submission pipeline.

- [Research report](REPORT_HACKAPERTUS_OST.md): original measurements,
  withdrawn comparisons, ablations and unverified claims.
- [Research integrity history](research_integrity_history.md): dated audit
  findings and remediation evidence, including unresolved issues.
- [Original challenge notes](challenge_spec.md): historical interpretation;
  current requirements are assessed in [project status](../PROJECT_STATUS.md).
- [Pre-cleanup README](README_before_cleanup.md): verbatim historical snapshot.
  Its old paths, links and run instructions are archival text, not current
  instructions. In particular, its `make run` and v1.1 claims are superseded.

Historical scripts remain in `../../src/` to preserve imports and reproduction
paths. Existing scratch reproducers remain in `../../tmp/`; their purpose and
continued value are uncertain, so none was deleted. Two hard-coded import paths
were made relative after the move. Other old commands may need the project
working directory or `PYTHONPATH=src`; these probes are not supported entry points.
Original raw experiment results remain in ignored `../../data/`. They are local
provenance, not guaranteed available in a fresh clone.

For legacy OCR reconstruction only, from `track_2a/`:

```text
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets.git repos/VotingBooklets
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets-mono.git repos/VotingBooklets-mono
```

Skip checkouts already present. These large downloads are unnecessary for
`make run`. See [RUNNING.md](../RUNNING.md) for current instructions.
