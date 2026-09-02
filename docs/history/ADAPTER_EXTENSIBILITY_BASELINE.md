# DGraInsight Adapter Extensibility v1 baseline

Captured before implementation on 2026-08-31 from Git commit
`e383a3863fba78e86538b27b8fa7dad1873d42e7` with a clean worktree.

## Regression commands

| Gate | Baseline result |
|---|---|
| `python -m unittest discover -s tests -v` | PASS — 38 tests in 11.889 s |
| `npm run test:web-graph-regression` | PASS — DGraFormer, MSGNet, and MTGNN |
| `npm run test:web-session-v2` | PASS — TypeScript validator and browser import regression |
| `npm run build` | PASS — TypeScript and Vite production build |

The Python suite includes the frozen DGraFormer and MSGNet candidate-level `D`, raw-p,
BH-q, supported-status and family checks; exact graph-core preservation for DGraFormer,
MSGNet and MTGNN; and Python plus JSON Schema Session v2 validation.

## Frozen asset identities

| Asset | SHA-256 |
|---|---|
| `public/data/evidence/dgraformer_etth1_session_v2.json` | `e8d7426985d1abf36676da26f46928ea77f184a0ebc5805ca53cd3b0d261367e` |
| `public/data/evidence/msgnet_etth1_session_v2.json` | `6588023258c319993c8c836631432a4cdfc2604caf3817a9bdb2eadd1bbee0bd` |
| `tests/fixtures/mtgnn_quick_session_v2.json` | `6d57056b98a942d82eddd2633f56abed6678b02c61cb6d9bdd4cf0008d7d1cef` |
| `tests/fixtures/pipeline_v2_graph_baseline.json` | `8ebba23be8a153881247229892102536fbac1899006443904f14e55e5999708d` |

These assets are frozen inputs/expected outputs. Adapter Extensibility v1 must not rewrite
them. The same commands and hashes are the post-change regression gates.

## Baseline boundaries

- Offline Python executes model source, preprocessing, checkpoint load, graph extraction,
  graph overrides, controls and Session v2 export.
- The browser validates and reads Session v2. It executes no Python adapter or checkpoint.
- Quick Inspection is checkpoint-backed, descriptive case evidence with formal inference
  explicitly not evaluated.
- Frozen Formal Evidence Audit is separate and protocol-driven.
