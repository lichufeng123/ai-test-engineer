# Optional defect submission adapter

The framework exposes a domain-neutral `ai-test defect-*` command family. An explicitly configured local CLI implements the `defect-cli-v1` protocol. Existing project adapters keep ownership of authentication, team routing, version policies, media upload and repair. The public framework does not copy private tracker code or embed personnel, credentials or internal endpoints.

Without a global console-script install, invoke `./bin/ai-test` from the framework root, or use its absolute path from a private project. Do not copy the framework into a business repository.

## Local configuration

Generate a runtime-only configuration after reviewing the adapter source:

```bash
ai-test defect-adapter-config \
  --command /absolute/path/to/reviewed-defect-cli \
  --asset /absolute/path/to/its-core.py \
  --asset /absolute/path/to/its-transport.py \
  --asset /absolute/path/to/its-browser-bridge.mjs \
  --output ~/.config/ai-test/defect-adapter.json
```

For a Python script without an executable entrypoint, repeat `--command` with the absolute interpreter and script paths, in that order. Every command component must be a file; no shell fragments, free-form flags or remote executables are accepted. Include all reviewed source dependencies via `--asset`. The configuration stores paths and SHA-256 values, never passwords or tokens. Regenerate deliberately after reviewing adapter code changes; the wrapper blocks code drift rather than silently updating hashes.

Discovery order: explicit `--adapter`, `AI_TEST_DEFECT_ADAPTER`, project `.ai-test/defect-adapter.json`, user `~/.config/ai-test/defect-adapter.json`. Keep runtime configuration out of public version control. The configuration expresses trust in local executable code; hashes detect changes, not maliciousness or business authorization.

## Execution workflow

1. Start a saved plan and execution log under the existing standard/rapid rules.
2. `ai-test defect-versions` returns at most three candidates. Show them to the user; no automatic latest-build choice.
3. `defect-select --run <private-run/defect-run.json> --run-id <existing-execution-id> --scope <scope> --build <chosen-id> --confirmed-by <actual-person>` binds the human selection to this execution. Repeat `--build` for multiple versions. The project adapter verifies the selection and persists its canonical run file.
4. Collect evidence, distinguish product defects from environment/fixture/cache/async/script errors, and confirm the target candidate. Adapter-specific inputs are documented by the project. The common input references `source=automation`, `triage_file`, `candidate_id` and a stable issue ID. Both triage and selection must match the current execution ID.
5. Preview with `defect-draft --input <issue.json> --run <defect-run.json>`.
6. If this run is authorized to submit defects, call `defect-submit --execute --input <issue.json> --run <defect-run.json> --output <private-receipt.json>`.
7. Only exit code 0 and `status=verified` count as complete submission. Record the Bug reference against the case/probe, issue and execution. Routing uncertainty remains visible as `needs_owner_confirmation`; ask the owner instead of inventing responsibility.

The automatic path checks candidate identity and run binding locally, then requires the provider to execute its full authoritative confirmation and evidence gates. A failed assertion alone is not a product defect. Standard-case requirements must not be forged for a rapid probe; if the provider lacks a rapid contract, retain the draft/blocker for standard follow-up and continue other authorized probes.

Images belong inline in reproduction steps, videos in attachments. The provider verifies loaded images, video attachment identity/content, and intended fields. Its successful result must include positive Bug ID, `status=verified` and `evidence.verified=true`. The framework adds `product_verdict=not_evaluated`: registering a defect does not authorize business writes or promote a test outcome to product acceptance.

`defect-verify` rechecks an existing submission without creating a new one. For interrupted creation, inspect the private adapter's existing receipt and reconcile by its stable marker before `defect-submit --execute ... --resume-bug-id <confirmed-id>`. The wrapper runs the provider once, with no shell and no network retry. A timeout is an unknown state, not permission to repeat creation. Keep the same issue ID and run file. Do not delete pending receipts or concurrent locks to bypass safety.

## Python/CI invocation

```python
import json
import subprocess

completed = subprocess.run([
    'ai-test', 'defect-submit', '--execute',
    '--input', str(private_run / 'issue.json'),
    '--run', str(private_run / 'defect-run.json'),
    '--output', str(private_run / 'issue-receipt.json'),
], capture_output=True, text=True)
receipt = json.loads(completed.stdout)
if completed.returncode == 0 and receipt['status'] == 'verified':
    record_bug_reference(case_or_probe_id, receipt['bug_id'])
else:
    record_submission_blocker(receipt)  # preserve original issue ID and provider receipts
```

The framework can run a headless adapter if the project provides one. The currently configured private adapter uses API for login/version/query/create/readback and authenticated Ego Lite for image editor upload, video attachment upload, and visual/DOM verification. This adapter requires a browser-capable execution node; installing this public package does not make it suitable for browserless CI. Missing runtime credentials or browser identity blocks only submission. Real notifications remain separately authorized.

## Protocol and validation

The local provider accepts `versions`, `select`, `draft`, `submit --submit`, and `verify` with the argument names passed by these commands. `select` additionally accepts `--run-id` and saves exactly the run returned on stdout. Its `versions` reply is `needs_selection`; `draft` replies `draft`; submit/verify reply `verified` only after readback. Nonzero exits or unexpected replies are blocked. Unstructured stdout/stderr is not echoed into reports, and artifacts with credential fields are rejected. A separate safe `--output` JSON is updated to blocked on preflight/provider failure so an earlier success cannot remain misleading. Provider-owned `<run>.receipts/` state is reserved and cannot be used as wrapper output. Private detailed recovery state stays with the project adapter.

Engineering regression uses synthetic provider scripts in isolated temporary directories and the existing private adapter tests. It performs no real tracker writes. Provider hashes, candidate/run binding, explicit write authorization, output-clobber protection, protocol status, and installed CLI entrypoints have negative controls. See the run-local verification report for the exact revision and limits.
