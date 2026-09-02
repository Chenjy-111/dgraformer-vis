# DGraInsight V1 Safe Removal Report

Date: 2026-08-31
Backup: `codex/backup-pre-v1-removal` at `599f15662cc71cccaab0bca49fe376b115ee8f6e`
Constraints honored: no training, sample/test reselection, statistical-protocol change, visual redesign, commit, push, release, or remote modification.

## A. V1 removal

1. Session v1 runtime completely deleted: **YES**.
2. Browser import compatibility completely deleted: **YES**.
3. `--legacy-v1` deleted: **YES**.
4. `--session-version 1` deleted: **YES**.
5. v1 schema deleted: **YES**.
6. v1 Python validator/parser deleted: **YES**.
7. v1 TypeScript validator/types deleted: **YES**.
8. Legacy empirical inference deleted from runtime/artifacts: **YES**.
9. Old case-level BH deleted: **YES**.
10. Old B=100 significance workflow deleted: **YES**.

## B. Shared/current safety

11. Current adapters accidentally deleted: **NO**; DGraFormer, MSGNet, MTGNN remain.
12. Graph utilities accidentally deleted: **NO**; graph extraction/intervention utilities and V01–V09 remain.
13. Baseline/intervention data accidentally deleted: **NO**; protected current operands/trajectories were migrated before deletion.
14. MTGNN current fixture: `tests/fixtures/mtgnn_quick_session_v2.json`.
15. Required dependency on root `dgrainsight_session.json`: **NO**.
16. Required ignored source/fixture: **NO**. Installed environments are ignored by design, not repository inputs.

## C. Pipeline v2

17. V01–V11: **PASS**.
18. Config v2: **PASS**.
19. Quick Inspection v2: **PASS** (native runtime, all unique eligible controls, formal inference unavailable).
20. Formal Audit v2: **PASS**.
21. Session v2 exporter: **PASS**.
22. Session v2 semantic + JSON Schema validators: **PASS**.

## D. Scientific regression

23. DGraFormer local: **1/8**.
24. DGraFormer all-retained: **1/4**.
25. MSGNet single-scale: **27/126**.
26. MSGNet all-scale: **14/42**.
27. DGraFormer frozen p/q unchanged: **YES**, including `0.0010998900109989002 / 0.008799120087991202` and `0.00009999000099990002 / 0.00039996000399960006`.
28. MSGNet 14 tests unchanged: **YES**.
29. MSGNet family sizes unchanged: **126 / 42**.
30. MSGNet 41 unique controls unchanged: **YES**.

## E. Graph

31. DGraFormer graph regression: **PASS**.
32. MSGNet graph regression: **PASS**.
33. MTGNN graph regression: **PASS**.
34. Graph tensor/hash change: **NO**. A Web regression fixture was narrowed from whole-file identity to protected MTGNN graph-core identity so v2 provenance migration does not masquerade as a graph change.
35. Baseline prediction change: **NO**.

## F. Web v2

36. DGraFormer Dynamic Graph displays: **PASS**.
37. DGraFormer relation selector: **PASS**.
38. DGraFormer evidence tabs: **PASS**.
39. DGraFormer evidence/trajectory: **PASS**.
40. MSGNet Dynamic Graph displays: **PASS** (large frozen asset load completed).
41. MSGNet edge click: **PASS**.
42. MSGNet single/all-scale tabs: **PASS**.
43. MSGNet trajectories: **PASS**.
44. Quick Inspection v2 browser contract: **PASS**.
45. Formal Session v2 import/validation route: **PASS**.
46. Retired session import: explicit fail-closed message: `Session v1 is no longer supported by the current DGraInsight release. Please generate a Session v2 audit.`

## G. Tests

47. Current Python test count: **38**.
48. PASS count: **38**.
49. SKIP count: **0**.
50. Legacy-only tests removed: **44 total** (35 old passing expectations + 9 old missing-artifact skips).
51. TypeScript compile: **PASS**.
52. Vite build: **PASS**.
53. Session v2 Python/Schema/Web tests: **PASS**.
54. Graph regression: **PASS**.
55. Browser smoke: **PASS**.
56. Browser console errors/warnings: **0** during final interaction smoke.

## H. Fresh copy

57. Final tracked-candidate snapshot: **YES**, `.tmp/public-snapshot-v2-only-final` (2611/2611 candidate files copied; an interrupted partial predecessor was not reused).
58. Existing clean venv reused: **YES**, `.tmp/public-snapshot/.venv` (Python 3.9.13, torch 2.1.1+cpu, numpy 1.24.3).
59. Untracked runtime/source dependency: **NO**.
60. Formal CLI in final snapshot: **PASS**.
61. Session v2 validation in final snapshot: **PASS**.
62. Web build in final snapshot: **PASS**.
63. Required candidate files included: **YES**; `third_party/` and private/local files excluded.

## I. Legacy search

64. Remaining `Session v1` references: only the explicit unsupported constant/test and this audit documentation.
65. Remaining `empirical_p` references: only v2 rejection guards/schema negative tests and historical migration reports.
66. Remaining case-BH references: only v2 rejection guards/negative tests and historical migration reports.
67. Remaining B=100 references: historical migration reports only.
68. Retention reason: fail-closed security/semantic validation, regression-negative coverage, or archived migration evidence under `docs/migration/`; none executes old inference.
69. Current runtime occurrence of old inference/compatibility: **0**.

## J. Final file state

70. Files deleted: recorded in `DGRAINSIGHT_V1_REMOVAL_MANIFEST.md`; includes v1 runtime/schema/UI/tests, legacy inference tools/configs, and old artifacts.
71. Files renamed/moved: Quick runtime, MSGNet frozen directory/metadata, and migration reports.
72. Current fixtures added: MTGNN Quick Session v2, MSGNet graph core, compact DGraFormer formal operands, updated graph baselines.
73. Documentation updated: **YES**, README and current CLI/Session/reproducibility/adapter docs are v2-only.
74. Uncertain current dependency: **NO**. Unresolved `third_party/` licensing content is excluded and not required.

## Final status

V1 SAFE REMOVAL PASS
