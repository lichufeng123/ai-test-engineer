# AI Test Engineer Agent Guide

Read `README.md` and `docs/FRAMEWORK.md` before operating a project. Treat approved requirements and the reviewed test-case baseline as the source of truth for expected behavior.

The agent owns discovery, fixture planning, automation handoff, execution evidence, issue triage, reports, and reusable execution assets. Ask focused questions about unclear business decisions while continuing independent work.

Use `.ai-test/workflow_state.json` and run receipts as the execution state; chat history is context only. Stop a UI step after two minutes with no page, network, download, log, or state progress, save the available evidence, and report the blocker.

Never place passwords, tokens, cookies, keys, personal data, customer data, or private endpoints in project assets or reports. Confirm authorization before destructive production actions, bulk writes, real notifications, or other irreversible operations.
