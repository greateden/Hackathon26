# Thursday demo delivery

## Actual scope and readiness

The research experience at `docs/experience/courage-to-be-wrong/index.html` is
static HTML/CSS/JavaScript showing recorded results. It executes no inference.
It loads only sibling `styles.css`, `facts.js`, and `app.js`; no build, CDN,
secret, absolute asset path or server API is required. It is suitable for a
GitHub Pages subdirectory. Safari localhost rendering and layer navigation were
checked on 14 October. It is not yet published; no public URL or recording exists.
GitHub's source preview does not execute it. The report links the actual repository
README artefact, accessible to authorised repository reviewers, not a fictitious site.

Local preview from repository root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory track_2a/docs/experience/courage-to-be-wrong
```

Open `http://127.0.0.1:8765/`. This is a local preview address, not a deployment.

## Aline: Pages, Thursday morning

After all-three approval and organiser confirmation of visibility/access:

1. Confirm the repository's plan permits the intended Pages access; do not change
   repository visibility merely to enable Pages.
2. In a separately reviewed Pages workflow, check out the approved commit, use
   GitHub's `configure-pages`, `upload-pages-artifact`, and `deploy-pages` actions.
   Upload **only** `track_2a/docs/experience/courage-to-be-wrong/`, with permissions
   `contents: read`, `pages: write`, `id-token: write` and the `github-pages`
   environment. Pin action versions according to current GitHub documentation.
   No workflow is installed or triggered by this preparation.
3. Prefer an explicit manual workflow trigger for the first reviewed deployment.
   The branch-source `/docs` option cannot directly select this nested directory.
4. Use the actual URL returned by deployment; test all five tabs and case controls
   from a reviewer account/browser. Check asset responses and no console errors.
5. Replace the report's Demo link with that tested URL, retaining the statement
   that it displays recorded results. Keep a repository artefact fallback.

## Mikal: real pipeline recording, Thursday lunch/afternoon

Record about 60–90 seconds with the operating system's screen recorder; audio is
optional. Prepare credentials privately before recording, with shell tracing off.
Hide unrelated windows, notifications, home-directory paths and account details.
Do not show `env`, `.env`, credential files, shell history or `docker inspect`.

- Show `git rev-parse --short HEAD`, the explicit model name
  `swiss-ai/Apertus-v1.5-70B`, and the non-secret CSCS endpoint.
- Show and execute the real command:
  `REQUEST_FILE=/app/data/examples/advanced-entailment.json make run`.
- Show the request's vote/claim and official booklet URL; the run must use actual
  PDF retrieval. Explain any cached encoder/PDF and cut waiting time only with
  a visible annotation; never replace execution with an animation.
- Show actual official JSON: label, page/text evidence, input/output tokens,
  inference latency; show `echo $?` immediately after make.
- Briefly state that neutral can still be rejected by the identity gate. This is
  a successful-case demonstration, not a benchmark or proof of universal validity.
- Review the recording for secrets and personal information. Save locally and
  obtain team approval before any third-party upload. Only then add a working,
  reviewer-accessible video link. Screenshots alone are not the planned deliverable.

The release session used all four authorised inference calls. Recording is a
future teammate action and will require a fresh authorised call; none is claimed
as completed here.
