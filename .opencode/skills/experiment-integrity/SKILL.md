---
name: experiment-integrity
description: Protect reproducibility, provenance, and valid evaluation when changing Hackathon26 experimental code or records.
compatibility: opencode
metadata:
  scope: "Hackathon26"
---

# Experiment integrity

Use this skill for experimental work in Hackathon26.

- Preserve frozen plans, completed predictions, manifests, raw records, and dataset provenance.
- Verify configuration, prompt, input, and evidence hashes when they identify a run.
- Prevent gold labels, reference passages, and other evaluation-only data from leaking into model or retrieval inputs.
- Retain failures and missing results in the correct denominators; never silently convert them into predictions.
- Distinguish raw accuracy from strict accuracy, and citation provenance from semantic support.
- Keep experiment attempts append-only. Do not overwrite completed runs or silently change the evaluated method.
- Avoid new model inference, downloads, or paid calls unless explicitly authorised.

Before changing experimental code, determine whether the change would invalidate historical measurements. If it would, report the incompatibility and require a versioned new method or authorised rerun rather than altering a frozen implementation silently.
