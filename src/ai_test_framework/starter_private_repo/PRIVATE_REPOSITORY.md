# Private test asset repository (starter)

This directory is the bundled reference skeleton for a **private, controlled** test
asset repository. It is copied by:

```bash
ai-test private-scaffold --root ./my-private-assets \
  --name "Example Products" --system-id example-products \
  --environment sit --platform web
```

Existing files are never overwritten.

## Why a separate repository

The public framework ships workflows, schemas, templates, playbooks and synthetic
examples only. Real accounts, internal domains, private collaboration documents,
business rules, real screenshots and execution evidence must live in a private
repository or a controlled file space. See `docs/FRAMEWORK.md` section 17.

## What this skeleton contains

```text
<private-repo>/
├── ai-test.json                      # project profile written by `ai-test init`
├── knowledge/
│   ├── INDEX.md                      # human-readable knowledge entry point
│   ├── manifest.json                 # generated registry manifest with real hashes
│   ├── system/ecosystem-map.md       # placeholder system map
│   ├── modules/example-module/       # placeholder business topology
│   └── test-risks/                   # placeholder omission-risk rules
└── scripts/
    └── knowledge_registry.py         # validate / load / refresh, local-only
```

## How the framework connects

The private repository is the project root for every `ai-test` command
(`--root <private-repo>`). Only three commands read across the boundary:

| Command | Purpose |
| --- | --- |
| `ai-test knowledge-audit --private-root <private-repo> --feature F --stage S` | Runs `validate` then `load`, then re-checks every returned path and hash |
| `ai-test baseline-snapshot --private-root <private-repo> --requirement-id REQ-X` | Re-checks a work item's local baseline identity and hash |
| `ai-test doctor --root <private-repo> --private-root <private-repo>` | Offline install health plus knowledge manifest hash pre-check |

Contracts: `schemas/knowledge-registry-manifest.schema.json` and
`schemas/knowledge-registry-load.schema.json`. A passing receipt proves local path
and hash consistency only; it does not prove the agent read the files, does not
certify a remote Current baseline, and does not authorize any business write.

## Next steps

1. Run `python3 scripts/knowledge_registry.py validate`.
2. Replace the placeholder knowledge with reviewed content.
3. Run `python3 scripts/knowledge_registry.py refresh` then `validate` again.
4. Add a secret scan and run it before every commit.
5. Never commit credentials, cookies, tokens, customer data, screenshots, videos,
   downloads or execution evidence; keep run evidence in an external archive or an
   ignored `runs/` directory.
