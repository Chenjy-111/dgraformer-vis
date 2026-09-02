# DGraInsight V1 Removal Manifest

Date: 2026-08-31
Recovery point: local branch `codex/backup-pre-v1-removal`, commit `599f15662cc71cccaab0bca49fe376b115ee8f6e` (not pushed).

## Deleted runtime, schema, UI, and tests

- Python: `dgraudit/session.py`, `dgraudit/local_audit.py`, the v1 exporter/generator, legacy case-inference/statistical-catalog CLIs, and their obsolete analysis scripts.
- Schemas/parsers: `schemas/dgrainsight_audit_session_v1.schema.json`, the Python v1 parser/validator, `src/data/auditSession.ts`, `tests/auditSessionValidator.mjs`, and `tsconfig.audit-session-validator.json`.
- UI: `src/components/ImportedAuditWorkspace.tsx`, unused legacy evidence components, and `legacy/v1/`.
- Tests: v1 schema/export/round-trip tests and retired case-level empirical/BH catalog tests. Pre-removal inventory was 73 PASS + 9 SKIP; current inventory is 38 PASS + 0 SKIP. The 44 removed cases were 35 legacy-only passing expectations and 9 obsolete missing-artifact skips.
- Config/docs/scripts: v1 export configs, old empirical/BH/B=100 catalog configs, stale reproduction instructions, and old migration clutter.

## Deleted artifacts

- `artifacts/sessions/`
- `artifacts/runs/`
- `artifacts/cross_sample_validation/`
- old root-generated session files
- old MSGNet relation-level statistical freeze outputs/reports

Large `.npy` deletions under the historical MSGNet directory appear in Git as directory replacement. Their required frozen trajectories were preserved byte-for-byte under the current directory.

## Renamed or migrated

- `dgraudit/local_audit.py` → `dgraudit/quick_audit.py`, with native v2 construction and no legacy inference.
- `artifacts/msgnet_cross_test_v1/` → `artifacts/msgnet_frozen14/`, with current `formal_protocol_v2.json`, `candidate_family_v2.json`, and `formal_manifest_v2.json`.
- Pipeline/Web migration reports → `docs/migration/`.
- DGraFormer current formal operands → `artifacts/dgraformer_frozen40/`.

## Current fixtures added

- `tests/fixtures/mtgnn_quick_session_v2.json`
- `tests/fixtures/msgnet_graph_core_baseline.json`
- updated `tests/fixtures/pipeline_v2_graph_baseline.json`
- updated `tests/fixtures/web_graph_baseline_v2.json`

All deletions are recoverable from the local backup commit. No commit, push, release, or remote mutation was performed.
