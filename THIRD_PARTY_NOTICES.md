# Licensing scope and third-party notices

> **Submission update: 15 October 2026.** This inventory describes the tracked
> source checkout **and the actual production Docker build**, which are not the
> same distribution artefact. The notices below do not grant rights over upstream
> material; any unresolved redistribution question requires human review.

Team-authored source code is licensed under the root Apache-2.0 `LICENSE`.
Team-authored reports and documentation are intended to be CC-BY-4.0.
The event's stated default for newly submitted team-authored datasets is
CDLA-Permissive-2.0. Those project licences do **not** relicense original
booklets, model weights, datasets or third-party packages.

## What is distributed where

- **Git repository:** contains team code, documents, limited experimental
  records, fixtures, and quoted text. It does not contain the official Apertus
  weights, full voting-booklet PDF corpus, or the full evaluation dataset.
  Existing fixture/evidence quotations are not automatically licensed by us.
- **Production Docker image:** the current Dockerfile downloads and **bundles**
  the pinned SentenceSwissBERT encoder under
  `/opt/models/sentence-swissbert` at *build time*, including model files and
  tokenizer assets. This statement replaces an earlier, incorrect notice
  claiming that the weights were absent from the image. The Docker image
  does **not** include Apertus LLM weights; inference uses an authorised API.
- **Development/tests:** the current Dockerfile also copies `tests/`,
  potentially including development fixtures with gold labels. The production
  release should separate or exclude these from the image after verifying
  no runtime import depends on them. That is an evaluation-integrity concern,
  independent of their upstream copyright terms.

## Third-party components and upstream terms

- **HackApertus template:** Apache-2.0, https://github.com/HackApertus/project-template
- **OST MNLI over Swiss voting booklets data:**
  https://huggingface.co/datasets/OSTswiss/MNLIoverSwissVotingBooklets
  The upstream dataset's exact licensing, attribution and permitted
  redistribution must be checked for any included extracts/fixtures. The
  project does not relicense the upstream dataset under CDLA-Permissive.
- **Swiss Federal Chancellery voting booklets:** original PDFs are linked to
  their official source URLs and are excluded from the source checkout.
  Small source excerpts in recorded evidence or demos are attributed; the
  applicable source reuse terms require human review before public release.
- **SentenceSwissBERT:** https://huggingface.co/jgrosjean-mathesis/sentence-swissbert
  The model card identifies **CC-BY-NC-4.0**, not Apache-2.0. Its
  redistribution, attribution, non-commercial scope, and accompanying notice
  obligations must be reviewed **before publishing an image containing its
  weights**. A research/hackathon setting does not automatically resolve
  licence compatibility. Keep the model's own copyright/licence information;
  seek clarification or an authorised alternative if necessary. The project
  licence does not supersede these upstream rights.
- **Apertus v1.5 and CSCS:** model and provider terms apply separately.
  The project does not relicense model weights or confer access to the
  external inference service/API credentials.
- **Python/PyTorch/Transformers and other system/container dependencies:**
  retain their respective upstream licences. Installing packages into an
  image is distinct from licensing them as team-authored source.

## Release checks for a team member

1. Confirm that any redistributed encoder weights may be distributed under
   the intended registry access and use; carry required attribution/licence
   text into the image and release notes as appropriate.
2. Inspect the final image for development gold fixtures and secrets; exclude
   material not required at runtime.
3. Verify rights/attribution for excerpts in the technical report and demo.
4. Publish only after explicit team approval, recording the source Git SHA,
   image tag, immutable digest and pull-access verification.

This file is a factual technical inventory, **not legal advice** or a claim
that all publication/redistribution permissions have already been confirmed.
