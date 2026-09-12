<!-- FRAMEWORK_VERSION: 0.2.0 -->

# AI Test Engineer

AI Test Engineer is a portable, evidence-first framework for guiding an AI agent through software testing. It connects requirement understanding, system and feature discovery, approved test-case baselines, fixture generation, execution, evidence review, reporting, and reusable execution assets.

The core uses Python's standard library, Markdown, and JSON Schema. It works with any AI assistant; adapters describe optional integrations for Codex, Playwright, and Minium.

## Quick start

```bash
python3 -m pip install -e .
ai-test init ./my-test-project \
  --name "Member Portal" \
  --system-id member-portal \
  --environment test \
  --platform web
```

For a new system, plan discovery before testing a feature:

```bash
ai-test discovery-plan \
  --project ./my-test-project/ai-test.json \
  --environment test \
  --platform web \
  --product-version 1.0.0
```

Use a reviewed test-case baseline as the single source of truth. The framework records its stable case IDs and hash in an execution handoff; UI automation is not a second case-management system.

Generate deterministic test fixtures:

```bash
ai-test data-generate \
  --spec templates/fixture-spec.example.json \
  --output ./fixtures/generated
```

Check evidence and embedded report media:

```bash
ai-test evidence-check \
  --manifest ./runs/2026-09-12/evidence_manifest.json \
  --root ./runs/2026-09-12 \
  --report ./runs/2026-09-12/report.md
```

Read the [framework handbook](docs/FRAMEWORK.md) for the complete workflow and the [playbooks](playbooks/README.md) for operational guidance.

## Project layout

- `src/ai_test_framework/`: CLI and reusable framework primitives.
- `playbooks/`: tool-independent testing procedures.
- `adapters/`: optional integrations and baseline guidance.
- `schemas/` and `templates/`: machine-readable contracts and safe examples.
- `examples/`: sanitized fixture examples.

## Development

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
ai-test docs-check --root .
```

Framework behavior, CLI commands, repository layout, or quality gates must update this README, `docs/FRAMEWORK.md`, and `framework-manifest.json` together.

## Security and privacy

Do not commit credentials, private endpoints, customer data, execution recordings, screenshots, downloads, caches, or production exports. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
