# Licensing scope and third-party notices

Team-authored source code is licensed under the root Apache-2.0 LICENSE.
Team-authored reports and documentation are CC-BY-4.0. The organiser's default
for newly submitted team-authored datasets is CDLA-Permissive-2.0; it does not
relicense upstream data. No original PDFs, model weights or full evaluation
corpus are added by this release.

Bounded review (14 October 2026): tracked source, tests, scratch scripts,
static HTML/CSS/JavaScript, figures, small fixtures and compact evidence records
were inventoried; no vendored third-party source library or conflicting source
notice was identified. This is a source review, not a legal opinion or an audit
of every dependency. Existing attribution is retained.

- HackApertus template: Apache-2.0, https://github.com/HackApertus/project-template.
- Evaluation examples: OSTswiss/MNLIoverSwissVotingBooklets v1.1, recorded by
  `fetch_eval_data.py` as MIT. The two new request fixtures reproduce only claims,
  vote names and source URLs, attributed in `data/examples/README.md`; upstream
  terms continue to apply. They are not relicensed under CDLA.
- Swiss Federal Chancellery booklets: linked to their official source URLs;
  original PDFs remain ignored. Short source excerpts in existing evidence and
  model-generated reasoning retain attribution. Redistribution of those existing
  excerpts requires human review of applicable source terms before publication;
  project licences do not grant rights in third-party material.
- SentenceSwissBERT: model-card CC-BY-NC-4.0 terms, not Apache-2.0. Weights are
  downloaded separately, not distributed in the source or image. Commercial use
  and redistribution need a separate compatibility review.
  https://huggingface.co/jgrosjean-mathesis/sentence-swissbert
- Apertus v1.5 model/provider terms apply separately to CSCS access and managed
  downloads. Model identities are explicit; this project does not relicense
  weights or confer API access.
- Python/container dependencies retain their upstream licences. The Dockerfile
  installs them from their package sources; no dependency source is vendored.

Before public release, the team must confirm contributor authority and the
remaining excerpt/data permissions. No private API credential is distributed.
