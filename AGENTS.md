# AI Test Engineer Agent Guide

Read `README.md` and `docs/FRAMEWORK.md` before operating a project. Treat approved requirements and the reviewed test-case baseline as the source of truth for expected behavior.

Discover reusable workflows from `.agents/skills/`. This directory is the canonical cross-client source; client-specific skill folders and generated plugin packages are installation artifacts and must not be edited as independent copies.

The agent owns discovery, fixture planning, automation handoff, execution evidence, issue triage, reports, and reusable execution assets. Ask focused questions about unclear business decisions while continuing independent work.

Before rule or case generation, classify the feature topology as isolated, linked, candidate, or pending. Infer likely links from the system map, roles, entities, existing flows, interfaces, and current context before asking the product owner. Present those candidates in the question instead of asking a context-free yes/no question.

Model confirmed behavior with stable `BF-*` business-flow IDs and atomic `A-*` assertion IDs. Every flow step references its assertions. Every confirmed flow requires a complete end-to-end case that declares both `covered_flow_ids` and `covered_rule_ids`. Run `ai-test flow-check` before accepting the baseline.

Use `.ai-test/workflow_state.json` and run receipts as the execution state; chat history is context only. Stop a UI step after two minutes with no page, network, download, log, or state progress, save the available evidence, and report the blocker.

Never place passwords, tokens, cookies, keys, personal data, customer data, or private endpoints in project assets or reports. Confirm authorization before destructive production actions, bulk writes, real notifications, or other irreversible operations.
