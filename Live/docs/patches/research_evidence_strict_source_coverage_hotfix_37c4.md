# Research Evidence Strict Source Coverage Hotfix 37c4

Fixes a bad escaped-newline write from 37c3 and replaces the strict coverage
detector/checker with valid Python files.

Coverage now ignores AI/quant playbook missing-evidence text and only counts
source-like cards or user-approved recommendation cards as evidence.
