# DGraInsight Repository Classification

Audit date: 2026-08-31  
Scope: repository state before public-upload cleanup  
Policy: Session v2 is current; Session v1 is retained only for compatibility and historical reproduction.

## Classification rules

- `CURRENT_V2` is the formal cross-sample/cross-test pipeline and its frozen protocols.
- `LEGACY_V1` is the explicit single-case compatibility implementation.
- `SHARED` is used by both versions without importing v1 inference into v2.
- `WEB_CURRENT` is reachable by the default built-in browser workflow.
- `FIXTURE_CURRENT` may contain frozen source observations but is not a production Web payload.
- `FIXTURE_LEGACY` is retained only for v1 compatibility or migration regression.
- `GENERATED_*` is reproducible output, not source.
- `LOCAL_ONLY` and `PRIVATE_OR_UNPUBLISHABLE` must not be committed.
- `UNCERTAIN` files are preserved until the owner resolves them.

The table groups homogeneous file families. A row is an inventory record for every file matched by its path or glob.

| path | category | purpose | required_by_v2 | required_by_v1 | required_by_web | required_by_cli | required_by_tests | can_move | can_delete | should_publish | reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `dgraudit/v2/**` | CURRENT_V2 | Config/schema validation, controls, families, dependence, inference, session writer and runners | yes | no | indirect | yes | yes | no | no | yes | Formal Pipeline v2 implementation |
| `dgraudit/__main__.py`, `dgraudit/cli/audit.py`, `dgraudit/cli/validate_session_v2.py`, `dgraudit/cli/wizard.py` | CURRENT_V2 | Default v2 CLI and explicit legacy dispatch | yes | compatibility | no | yes | yes | no | no | yes | Default audit output is Session v2 |
| `dgraudit/adapters.py`, `dgraudit/validation.py`, `dgraudit/edge_discovery.py` | SHARED | Frozen model adapter contracts, V01-V09 validation and graph discovery | yes | yes | indirect | yes | yes | no | no | yes | Shared primitives; adapters are frozen |
| `dgraudit/local_audit.py`, `dgraudit/session.py` | LEGACY_V1 | Explicit Session v1 generation/export compatibility | no inference | yes | import only | explicit only | yes | no | no | yes | Runtime move would add compatibility risk; keep in place and label |
| `dgraudit/cli/*.py` not listed above | SHARED | Offline extraction, validation, catalog and historical reproduction tools | some | some | no | explicit | yes | no | review | yes | Not on default formal path; dependencies remain explicit |
| `schemas/dgrainsight_audit_config_v2.schema.json`, `schemas/dgrainsight_audit_session_v2.schema.json` | CURRENT_V2 | Current public schemas | yes | no | Session v2 import | yes | yes | no | no | yes | Required formal contracts |
| `schemas/dgrainsight_audit_session_v1.schema.json` | LEGACY_V1 | v1 compatibility schema | no | yes | v1 import | yes | yes | no | no | yes | Required for claimed compatibility |
| `configs/formal_audit_v2_*.json` | CURRENT_V2 | Frozen public formal Config v2 examples | yes | no | no | yes | yes | no | no | yes | Current Quick Start/reproduction inputs |
| `configs/local_audit_*.json`, `configs/phase1_registry.json`, `configs/msgnet_etth1*.json` | DOC_LEGACY | v1/local templates and historical preprocessing configuration | no | yes | no | explicit | some | yes | no | yes after sanitizing | Contain developer-machine paths in the pre-cleanup state |
| remaining `configs/*.json` | SHARED | Extraction/catalog protocol inputs | indirect | yes | no | explicit | some | no | no | yes | Referenced by scripts/tests or frozen provenance |
| `src/App.tsx`, `src/components/SessionV2Evidence.tsx`, `src/components/ImportedSessionV2Workspace.tsx` | WEB_CURRENT | Current built-in/imported Session v2 UI | yes | explicit branch only | yes | no | yes | no | no | yes | Default Web renders v2 evidence only |
| `src/data/auditSessionV2.ts`, `src/data/auditSessionV2View.ts`, `src/store/useAuditSessionStore.ts` | WEB_CURRENT | TypeScript v2 validation, loading and atomic v1/v2 routing | yes | compatibility | yes | no | yes | no | no | yes | Current production v2 validator/loader |
| `src/data/auditSession.ts`, `src/components/ImportedAuditWorkspace.tsx`, `src/components/AuditSessionImport.tsx` | LEGACY_V1 | v1 validation and graph/descriptive import compatibility | shared types | yes | explicit import only | no | yes | no | no | yes | v1 never supplies v2 formal evidence |
| `src/data/msgnetLoader.ts`, `src/components/MsgnetWorkspace.tsx`, `src/components/three/**` | WEB_CURRENT | Current graph loading and unchanged renderers | yes | no | yes | no | yes | no | no | yes | Graph paths/hashes are protected |
| remaining reachable `src/**` | WEB_CURRENT | Current website UI, stores, types and styles | indirect | import branch | yes | no | build | no | no | yes | Required by TypeScript/Vite dependency graph |
| `src/components/MsgnetDiagnosticCharts.tsx`, `MsgnetGlobalDiagnostic.tsx`, `MsgnetSingleScaleDetail.tsx`, `src/data/msgnetLegacyTypes.ts` | LEGACY_V1 | Retired legacy MSGNet statistical display modules/types | no | historical | no | no | compile | yes | yes after dependency check | Not imported by current App; old p/BH display code |
| `src/components/CombinedInterventionLab.tsx`, `InterventionJourney.tsx`, `GlobalInterventionJourney.tsx`, `EvidenceValidation.tsx` | LEGACY_V1 | Retired catalog-driven demonstration components | no | historical | no | no | compile | yes | yes after dependency check | Not imported by current App; legacy catalogs only |
| `public/data/evidence/dgraformer_etth1_session_v2.json` | GENERATED_CURRENT | Built-in DGraFormer formal Session v2 | yes | no | yes | no | yes | no | no | yes | Current production asset; no legacy case p/BH fields |
| `public/data/evidence/msgnet_etth1_session_v2.json` | GENERATED_CURRENT | Built-in MSGNet formal Session v2 | yes | no | yes | no | yes | no | no | yes | Current production asset; 73.30 MiB, below GitHub 100 MiB limit |
| `public/data/models/msgnet/etth1/graph_catalog_v2.json` | GENERATED_CURRENT | Current MSGNet graph-only catalog | yes | no | yes | no | yes | no | no | yes | Current graph source, zero legacy inferential fields |
| `public/data/index.json`, `public/data/metrics.json`, `public/data/samples/**` | WEB_CURRENT | DGraFormer graph/sample/baseline demo data | indirect | historical | yes | no | graph regression | no | no | yes | Protected current graph assets |
| `legacy/v1/artifacts/public-data/**` | GENERATED_LEGACY | Retired v1 catalog/case inference artifacts | no | historical export/tests | no current fetch | old tools | v1 tests | no | no | yes, labeled legacy | Isolated from production Web after dependency audit; contains historical empirical p/BH |
| `tests/test_pipeline_v2.py`, `tests/auditSessionV2Validator.mjs`, `tests/sessionV2WebRegression.mjs` | TEST_CURRENT | Pipeline/Session/Web v2 validation and frozen statistics | yes | no | yes | no | yes | no | no | yes | Required public regression gate |
| `tests/fixtures/pipeline_v2_graph_baseline.json`, `tests/fixtures/web_graph_baseline_v2.json` | FIXTURE_CURRENT | Frozen graph tensor and prediction hashes | yes | no | yes | no | yes | no | no | yes | Highest-protection regression fixtures |
| existing `tests/test_*.py`, `tests/auditSessionValidator.mjs` | TEST_LEGACY | Shared adapter tests plus v1 compatibility validator/round trips | some | yes | v1 import | no | yes | no | no | yes | Required by full gate and compatibility claim |
| `artifacts/cross_sample_validation/**` | FIXTURE_CURRENT | Frozen DGraFormer candidate-level cross-sample inputs/results | yes | historical source | no | formal audit | yes | no | no | yes | Current v2 scientific fixture, not a Web production asset |
| `artifacts/msgnet_cross_test_v1/**` | FIXTURE_CURRENT | Frozen 14-test raw response/trajectory inputs used by v2 | yes | historical source | no | formal audit | yes | no | no | yes | Directory name is historical; current loader uses raw inputs, not case-level p/BH |
| `artifacts/sessions/dgraformer_etth1/dgrainsight_session.json`, `artifacts/sessions/msgnet_etth1/dgrainsight_session.json` | FIXTURE_LEGACY | Frozen v1 graph-core migration sources | yes (graph migration) | yes | no | formal fixture | yes | yes | no | yes or documented external asset | Large migration fixtures; never fetched by v2 Web |
| `artifacts/runs/3e834514.../**`, `artifacts/runs/a256ec935.../**` | FIXTURE_CURRENT | Frozen DGraFormer local/all-retained raw evidence inputs | yes | historical | no | formal audit | yes | yes | no | publish minimal safe subset | `dgraudit/v2/frozen.py` reads these runs; personal paths must be removed |
| `artifacts/runs/59573278.../**` | GENERATED_CURRENT | Frozen intervention source provenance | provenance | historical | no | no | indirect | yes | review | publish minimal manifest/catalog only | Current session provenance names this run; raw outputs are reproducible |
| all other tracked `artifacts/runs/**` | GENERATED_LEGACY | Historical phase outputs and development runs | no | historical only | no | old tools | no | yes | yes | no | No current import/JSON/schema/Web/CLI/test dependency; many embed personal paths |
| `artifacts/baseline/**`, `artifacts/baseline_final/**`, `artifacts/preflight/**`, `artifacts/cross_run/**` | GENERATED_LEGACY | Historical local validation output | no | historical | no | no | no | yes | yes | no | Generated records embed personal absolute paths |
| `artifacts/msgnet_checkpoints/**`, `artifacts/mtgnn_exchange/**` | PRIVATE_OR_UNPUBLISHABLE | Local model checkpoints and generated MTGNN sessions | external only | external only | no | optional local | no | no | local delete only | no | Redistribution/license not established; document hash/source instead |
| `third_party/**` | UNCERTAIN | Local upstream model checkout/data | optional | optional | no | external adapter | no | no | no | no pending license audit | Do not publish or delete until provenance/license is resolved |
| `experiments/**` | LOCAL_ONLY | Local training/checkpoint experiments | no | no | no | no | no | yes | local delete only | no | Reproduction scratch code with local-resource assumptions |
| `tmp/**`, `.tmp/**`, `*.log`, `dist/**`, `node_modules/**`, `*.tsbuildinfo` | LOCAL_ONLY | Build, validator, server and scratch output | no | no | no | no | no | yes | yes | no | Recreated locally; not source |
| `my_mtgnn_session*.json`, `dgrainsight_session.json` | GENERATED_LEGACY | Developer-generated Session v1 examples | no | optional | explicit import | no | no | yes | local delete only | no | Temporary generated sessions; canonical compatibility fixture is separate |
| `chatgpt_context_pack/**` | PRIVATE_OR_UNPUBLISHABLE | Local development handoff/context bundle | no | no | no | no | no | no | local delete only | no | Internal process material, not project source |
| `docs/AUDIT_SESSION_V2.md`, migration reports | DOC_CURRENT | Current protocol/session migration record | yes | explains boundary | no | yes | yes | no | no | yes | Formal v2 documentation |
| existing phase/handoff/catalog docs | DOC_LEGACY | Historical project and v1 pipeline documentation | no | historical | no | no | some | yes | no | yes under legacy docs | Must not be presented as current method |
| `.github/workflows/deploy.yml`, `vite.config.ts`, `package*.json`, TS/PostCSS/Tailwind configs | SHARED | Build and GitHub Pages deployment | indirect | import build | yes | no | yes | no | no | yes | Deployment paths/base must remain unchanged |
| `.gitignore` | SHARED | Exact local/private/generated exclusions | yes | yes | yes | yes | yes | no | no | yes | Must not hide current fixtures/assets |
| `README.md`, `docs/REPRODUCIBILITY.md`, `legacy/v1/README.md` | DOC_CURRENT | Public entry point and current/legacy boundary | yes | yes | yes | yes | yes | no | no | yes | Required for public release; absent before cleanup |
| `LICENSE` | UNCERTAIN | Repository source license | yes | yes | yes | yes | yes | no | no | owner decision required | No project license exists; this audit must not invent one |
| `CITATION.cff` | UNCERTAIN | Citation metadata | no | no | no | no | no | no | no | owner metadata required | No verified author/title/version metadata set was provided |

## Dependency-audit conclusions before movement

1. Current built-in Web fetches only the two Session v2 assets plus the MSGNet graph-only catalog and protected DGraFormer sample assets.
2. Legacy Session v1 enters only through explicit import/CLI branches. Its reader, validator, schema and descriptive workspace must remain.
3. The retired catalog-driven React modules are not imported by `src/App.tsx`; their old p/BH fields are therefore not current runtime dependencies.
4. `dgraudit/v2/frozen.py` requires the DGraFormer local/all-retained frozen inputs, cross-sample fixtures, MSGNet 14-test fixtures and two v1 graph-core migration sessions. These cannot be ignored or removed without a replacement fixture.
5. No current production Session v2 asset contains `empirical_p`, `bh_adjusted_p`, old supported-count fields, or `with_replacement: true`.
6. Pre-cleanup tracked output contains 1,098 files with Windows user paths; these are generated/provenance records, not graph or statistical values.

## Frozen baseline

- Tracked files before cleanup: 4,536.
- Tracked `artifacts/**`: 4,340 files, 117.00 MiB.
- Current untracked formal Web assets: 3 files, 81.01 MiB total.
- Files over 50 MiB: MSGNet Session v2 (73.30 MiB), DGraFormer v1 graph-core migration session (54.95 MiB).
- No file over 100 MiB was found.
- No `.env`, private key, SQL/database dump, or credential-pattern file was found.
