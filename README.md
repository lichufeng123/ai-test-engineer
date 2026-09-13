<!-- FRAMEWORK_VERSION: 0.4.0 -->

# AI Test Engineer

English | [简体中文](README.zh-CN.md)

AI Test Engineer is a portable, evidence-first framework for guiding an AI agent through software testing. It connects requirement understanding, system and feature discovery, approved test-case baselines, fixture generation, execution, evidence review, reporting, and reusable execution assets.

The core uses Python's standard library, Markdown, and JSON Schema. It works with any AI assistant; adapters describe optional integrations for Codex, Playwright, and Minium.

## Portable skills and optional plugin

The canonical workflow skills live in `.agents/skills/`, the cross-client discovery location used by Agent Skills-compatible tools. Opening this repository makes the project-scoped skills available to compatible agents. To install them for the current user:

```bash
ai-test skills-check --root .
ai-test skills-install --root . --client universal
```

Add `--client codex` to create a Codex compatibility link as well. Existing skills are never overwritten unless `--replace` is provided; replacement first moves them to a timestamped backup.

The repository is also an optional Codex/ChatGPT plugin source. The plugin package is generated from the same canonical skills, so it does not maintain a second copy:

```bash
ai-test plugin-build --root . --output ./dist/ai-test-engineer
```

The generated package contains `.codex-plugin/plugin.json` and the plugin-required `skills/` directory. Other clients can continue using `.agents/skills/` without installing the plugin. See [skill and plugin distribution](docs/skill-and-plugin-distribution.md).

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

Before generating cases, classify the feature as isolated, linked, or pending. Infer likely upstream and downstream links from the system map, role model, entity model, and existing context before asking the product owner. Confirmed flows receive stable `BF-*` IDs and reference atomic `A-*` assertions; every confirmed flow must have at least one complete end-to-end case.

Validate this contract with:

```bash
ai-test flow-check \
  --input ./rules/business-flows.json \
  --cases ./cases/approved-baseline.json \
  --matrix-output ./runs/latest/flow-coverage.json
```

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
- `.agents/skills/`: the single cross-client source for testing workflow skills.
- `plugin/plugin.json`: metadata used to build the optional plugin package.
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
