# DGraInsight

DGraInsight is an offline evidence-audit system for learned graph relations in multivariate forecasting models. The current repository is v2-only: Config v2 drives Quick Inspection or a frozen Formal Evidence Audit, both produce Portable Audit Session v2, and the browser validates and renders Session v2 without rerunning a model or recomputing statistics.

## Current evidence protocol

Formal evidence is candidate-relation-level across predeclared samples/tests. Each active unit stores the focal response, all unique eligible control responses, and `D = focal - control mean`. The formal layer then applies the declared dependence-aware primary inference and BH correction within frozen hypothesis families. Case records are descriptive and never carry formal p/q values.

Quick Inspection remains a real checkpoint-backed single-case workflow. It validates V01–V09, discovers native graph edges, performs real interventions, compares all unique eligible controls, and emits Session v2 with formal inference explicitly unavailable.

Supported adapters are DGraFormer, MSGNet, and MTGNN. Their graph extraction and intervention contracts are documented in [docs/SUPPORTED_LOCAL_AUDIT.md](docs/SUPPORTED_LOCAL_AUDIT.md).

## Install and test

Prerequisites are Python 3.9, Node.js 20 or newer, and npm.

```bash
python -m pip install -r requirements.txt
npm ci
python -m unittest discover -s tests -p "test_*.py"
npm run test:web-session-v2
npm run test:web-graph-regression
npm run build
```

No model training or sample/test reselection is part of these commands.

## Formal CLI reproduction

```bash
python -m dgraudit validate --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json
python -m dgraudit audit --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```

MSGNet uses `configs/formal_audit_v2_msgnet_etth1_frozen14.json` with the same three commands. Expected frozen results are DGraFormer 1/8 and 1/4 supported candidates, and MSGNet 27/126 and 14/42.

## Local Quick Inspection

Start from one of the Config v2 templates in `configs/local_audit_*.json`, or use the interactive wizard after pointing the template to local model source, checkpoint, and dataset files:

```bash
python -m dgraudit validate --config configs/local_audit_dgraformer_etth1.json
python -m dgraudit wizard --config configs/local_audit_dgraformer_etth1.json --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```

On Windows, `Start-DGraInsight-Audit.cmd` launches the same current workflow.

## Web

```bash
npm run dev
```

The built-in demo loads the two validated Session v2 assets under `public/data/evidence/`. The import panel accepts Session v2 only; retired session formats fail closed with an explicit regeneration message.

## Repository map

| Path | Role |
|---|---|
| `dgraudit/v2/` | Current statistical protocol, inference, families, and Session v2 writer |
| `dgraudit/adapters.py` | DGraFormer, MSGNet, and MTGNN adapter layer |
| `dgraudit/quick_audit.py` | Native Quick Inspection v2 runtime |
| `artifacts/dgraformer_frozen40/` | Minimal frozen DGraFormer formal operands |
| `artifacts/msgnet_frozen14/` | Frozen MSGNet formal operands and trajectories |
| `schemas/dgrainsight_audit_session_v2.schema.json` | Portable Session v2 JSON Schema |
| `src/` | Current Web v2 application |
| `tests/fixtures/` | Current graph and Session v2 regression fixtures |

See [docs/AUDIT_SESSION_V2.md](docs/AUDIT_SESSION_V2.md) and [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## External assets and release status

Raw third-party datasets, local checkpoints, upstream model source trees, secrets, and local environments are not included. Obtain model/data assets from their official sources and verify their hashes before a live audit.

This repository does not yet contain an owner-approved `LICENSE` or verified `CITATION.cff`; those remain publication-governance blockers and do not affect the local technical regression gates.
