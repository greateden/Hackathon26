# Third-party notices

**Licence information verified: 15 October 2026.**

This is a dated snapshot of third-party materials relevant to the VoteLens submission, not a commitment to monitor or maintain upstream licence information. The links below identify the upstream sources of applicable terms. Team-authored project licences do not override third-party rights.

## Bundled in the production Docker image

**SentenceSwissBERT**
- Source/model card: https://huggingface.co/jgrosjean-mathesis/sentence-swissbert
- Pinned revision: `7a91fa8a01af56c1f06060f7af3698ef5619e41c`
- Licence listed for this revision when checked: **CC BY-NC 4.0**
- Licence: https://creativecommons.org/licenses/by-nc/4.0/legalcode
- Distribution: the production image bundles model weights and tokenizer files at `/opt/models/sentence-swissbert`.
- Attribution: credit SentenceSwissBERT and its creator as identified in the upstream model card; preserve all attribution and licence notices required for distributing this version.

Other bundled Python, PyTorch, Transformers and system dependencies retain their respective licences. See the installed package metadata and upstream distributions for their individual terms.

## External sources, data and services

- **HackApertus project template:** https://github.com/HackApertus/project-template
- **OST MNLI over Swiss voting booklets:** https://huggingface.co/datasets/OSTswiss/MNLIoverSwissVotingBooklets
- **Swiss Federal Chancellery voting booklets:** https://www.bk.admin.ch/ (specific official PDF URLs are recorded in the project's data metadata; the full corpus is not bundled in the repository).
- **Apertus model:** https://huggingface.co/swiss-ai (Apertus LLM weights are not bundled in the production image).
- **CSCS inference service:** https://www.cscs.ch/ (service access and terms are separate from the project licence).

## Scope of this snapshot

External data, software and models retain their own terms. This file documents identified sources, versions and terms as checked on the date above; it does not guarantee future upstream terms will remain unchanged.

Before publishing an image containing SentenceSwissBERT weights, confirm that the intended distribution complies with the applicable CC BY-NC 4.0 conditions and that required attribution and licence materials accompany the distribution. This notice alone does not grant permission to redistribute third-party materials.
