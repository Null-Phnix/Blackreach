# Download verification walkthrough

This is a small demonstration of a specific reliability boundary in the Python
Blackreach agent. It does not exercise the separate native browser project.

## Run it

From a source checkout containing this change:

```sh
uv sync --locked --extra dev --extra server
uv run python examples/download_verification_demo.py
uv run pytest tests/test_download_action_contract.py -q
```

The demo uses temporary files and a simulated download transport. It calls the
real download action handler and content verifier. No model, network, browser,
API key, live account, or existing download database is used.

## What to explain

1. A request such as "download the PDF" establishes an expectation before the
   response arrives. The action accepts `expected_type: "pdf"`; a `.pdf` URL
   also supplies that expectation when the argument is omitted.
2. The server's filename is not proof. A landing page named `article.html` must
   not count as the requested PDF. The content verifier examines the bytes and
   applies its format/structure checks.
3. A valid ZIP is still the wrong artifact when a PDF was requested. Type
   agreement is checked before a format-specific validator can accept it.
4. Only accepted files reach download bookkeeping. Missing and rejected files
   do not increment recorded progress. Explicit HTML downloads remain allowed.

The demonstration shows four rejections (HTML, extensionless HTML, ZIP, missing
file), one accepted PDF and one deliberately requested HTML file. Tests also
exercise selector downloads, URL inference, duplicates and invalid arguments.

## What this does not prove

- It is not an autonomous open-web success-rate or speed benchmark.
- It does not prove the selected PDF is the requested paper. Document IDs,
  titles, source URLs, relevance and requested counts require separate checks.
- SHA-256 establishes byte identity/duplicates, not semantic relevance.
- The existing PDF validator performs heuristic structure checks, not a full
  PDF conformance or safety analysis.
- Extensionless downloads need the caller to supply the expected format.
  Prompt guidance helps a model provide it but is not a hard guarantee.
- The historical direct-fetch reserved-file cleanup issue is separate and
  remains open. This change does not rework authenticated downloads or SSRF.
- Broader agent telemetry currently distinguishes an executed action from
  download progress imperfectly; a skipped action may still be logged as an
  executed action. Use the artifact result and recorded count in this demo.

## Why this matters

Successful execution and successful task completion are different claims.
Keeping the requested artifact contract separate from the returned filename
prevents one concrete false-progress failure. It is a useful component to
evaluate alongside browser-driven or direct-function execution approaches.
