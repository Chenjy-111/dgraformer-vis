# DGraInsight V1 Removal Dependency Audit

Status: audit completed and resolved on 2026-08-31. This document records the pre-removal classification against local backup commit `599f15662cc71cccaab0bca49fe376b115ee8f6e` and the final disposition. No item classified `UNCERTAIN` was deleted.

## V1_RUNTIME_ONLY

- `dgraudit/session.py`: Session v1 catalog exporter, parser, semantic validator, and v1 statistical summary construction. Delete after current graph sources stop importing its outputs.
- Legacy inference portions of `dgraudit/local_audit.py`: empirical plus-one p, case-family BH, with-replacement bootstrap CI, legacy Session v1 assembly, validator call, schema references, flags, and provenance. Delete; do not carry these calculations into Quick Inspection v2.
- `dgraudit/v2/quick.py::upgrade_quick_session_v1`: v1-to-v2 converter. Replace with native Quick Inspection v2 construction.
- Legacy branches in `dgraudit/cli/audit.py`, `dgraudit/cli/wizard.py`, and `dgraudit/__main__.py`: remove `--legacy-v1`, `--session-version 1`, v1 output selection, and v1 temporary-session upgrade.
- `dgraudit/cli/export_audit_session.py`: v1-only exporter. Delete with its export configs.

## V1_UI_ONLY

- Session v1 types, parser, validator, discriminator, normalization, and lookup in `src/data/auditSession.ts` and the compatibility aliases/dispatch in `src/data/auditSessionV2.ts`.
- Legacy import wording and compatibility routing in `src/components/AuditSessionImport.tsx`, `src/components/ImportedAuditWorkspace.tsx`, and `src/store/useWorkflowStore.ts`.
- `legacy/v1/web/**`: isolated retired UI implementations. Delete.
- `tests/auditSessionValidator.mjs` and `tsconfig.audit-session-validator.json`: v1 browser-validator suite and build target. Delete; keep the Session v2 validator.

## V1_SCHEMA_ONLY

- `schemas/dgrainsight_audit_session_v1.schema.json`: v1 Session schema. Delete.
- `docs/AUDIT_SESSION_FORMAT.md`: v1 Session format documentation. Delete after current Quick Inspection documentation is consolidated into v2 docs.

## V1_TEST_ONLY

- `tests/test_audit_session_schema.py`, `tests/test_audit_session_export.py`, and `tests/test_audit_session_roundtrip.py`: v1 schema/export/round-trip expectations. Delete.
- Legacy inference assertions in `tests/test_local_audit.py` and v1-upgrade assertions in `tests/test_pipeline_v2.py`: replace with native Quick Inspection v2 coverage.
- v1 import-success assertions and compatibility notice assertions in Web tests: delete; replace with explicit fail-closed rejection coverage.

## V1_ARTIFACT_ONLY

- `legacy/v1/**`: retired Session v1 catalogs, historical Web copies, and explanation. Delete after all current references are removed.
- `artifacts/sessions/dgraformer_etth1/dgrainsight_session.json` and `artifacts/sessions/msgnet_etth1/dgrainsight_session.json`: legacy Session v1 export payloads. Their graph/model content remains current, but the files as a whole carry legacy inference and are not retained.
- `configs/export_session_dgraformer_etth1.json` and `configs/export_session_msgnet_etth1.json`: v1 exporter inputs. Delete.
- Legacy statistical run/catalog payloads containing case-level `empirical_p`/`bh_adjusted_p` are removable only when current frozen v2 reproduction no longer reads them. Current scientific response/control operands must be retained under current-specific names where still required.
- Ignored root `dgrainsight_session.json` and `my_mtgnn_session*.json`: local generated v1 outputs, not tracked and no current dependency. Remove from the final root; they are recoverable from the local backup/workstation state if needed.

## SHARED_CURRENT_DEPENDENCY

- `dgraudit/adapters.py`, graph extraction hooks, checkpoint loading, dataset loaders, baseline prediction, and intervention overrides: current, frozen, and protected.
- V01–V09 implementation in `dgraudit/validation.py`: current model/adapter validation. The legacy-shaped adapter configuration bridge is shared by the three current local templates and must be migrated carefully, not deleted blindly.
- Current portions of `dgraudit/local_audit.py`: tensor portability, metric calculation, graph-context serialization, exact context lookup, eligible-edge enumeration, real intervention replay, control identity collection, graph effect, baseline/truth/history serialization, and atomic output. Move to a v2-native Quick Inspection module before deleting the legacy file.
- `_context_id`, `_context_weight`, and `_resolve`, currently imported by `dgraudit/edge_discovery.py`: move to a current shared graph utility.
- `dgraudit/v2/**` formal pipeline, Config v2, controls, inference, dependence, Session v2 exporter/validator: current and protected. Internal parameter names that say `v1` must be renamed without changing data or scientific behavior.
- `public/data/evidence/*_session_v2.json`, `public/data/models/msgnet/etth1/graph_catalog_v2.json`, Web v2 views, graph renderer, adapters, and current formal configs: current and protected.
- Frozen DGraFormer/MSGNet response and control operands used by Pipeline v2: retain even when their directory name historically contains `v1`; rename only when references and checksums can be migrated without changing numeric content.

## CURRENT_FIXTURE_DERIVED_FROM_V1

- `tests/fixtures/mtgnn_exchange_session_v1.json`: currently supplies MTGNN graph/model regression truth only. Replace with `tests/fixtures/mtgnn_graph_core_baseline.json` containing no Session v1 inference records, local paths, private data, or legacy inferential fields.
- `tests/fixtures/pipeline_v2_graph_baseline.json`: current graph hashes and baseline predictions. Retain but update its wording/source paths so it describes current graph-core stability rather than Session v1 equivalence.
- The graph/model/sample/relation sections of the two tracked v1 sessions: current formal audit needs those values. Switch frozen loaders to the already tracked formal Session v2 assets and then delete the v1 payloads.

## UNCERTAIN

- `third_party/MTGNN/**`: untracked upstream source/data with unresolved public redistribution/licensing status. It is excluded from the backup commit and from deletion. It may be an external resource for live local MTGNN audit, but current tracked regression must not depend on it.
- Release metadata (`LICENSE`, final citation choice) remains a separate release decision. It does not block technical V1 removal and will be reported as `RELEASE METADATA PENDING`.

## Removal gates

1. Native Quick Inspection v2 must pass before `dgraudit/local_audit.py`, the v1 schema, or the v1 converter is deleted.
2. Frozen formal CLI and graph regression must pass after graph sources move away from legacy sessions.
3. Browser Session v1 input must fail closed with the required unsupported message; no conversion is allowed.
4. The tracked-only snapshot must contain every runtime/test fixture needed for all current gates.

## Final resolution

- Shared Quick Inspection capability moved to `dgraudit/quick_audit.py`; the old runtime was deleted.
- DGraFormer current formal inputs moved to `artifacts/dgraformer_frozen40/`; the old run catalogs and cross-sample output directory were deleted only after exact p/q and graph regression passed.
- MSGNet inputs moved to `artifacts/msgnet_frozen14/` with current v2 protocol/family/manifest metadata; raw frozen response/control operands and required trajectories were preserved.
- MTGNN current graph/Quick fixture is `tests/fixtures/mtgnn_quick_session_v2.json`; the retired fixture was deleted after Python 3.9-preserving graph hash verification.
- `third_party/` remains untouched and excluded. The final tracked candidate has no dependency on it.
- Final uncertainty count for the current tracked runtime is zero. License/citation ownership remains publication metadata, not a runtime dependency.
