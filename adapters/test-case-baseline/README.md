# Approved Test-Case Baseline Adapter

AI Test Engineer does not create a competing source of approved test cases. Connect the framework to your organization's reviewed test-case baseline, whatever tool stores it.

For every run, record the baseline identifier, stable case IDs, source references, and a content hash in the `automation_execution_bundle`. Automation scripts execute and report against that baseline; they do not silently redefine expected behavior or replace case review.
