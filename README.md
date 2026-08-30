# DGraInsight

DGraInsight currently uses the **Session v2 cross-sample relation-level audit pipeline**. Session v1 and its single-case inference are retained only for backward compatibility and historical reproducibility. New formal evidence must use Session v2.

DGraInsight audits learned graph relations in multivariate forecasting models. Offline Python code performs checkpoint-grounded graph interventions and statistical aggregation; the browser reads, validates, and displays the resulting immutable session. The browser does not rerun a model or recompute p-values/BH correction.

## Current system

The current formal pipeline uses:

- Session v2;
- cross-sample or cross-test candidate-level evidence;
- all unique eligible matched controls;
- per-unit excess response `D`;
- model/dependence-specific inference;
- frozen hypothesis families and family-level BH correction;
- explicitly separated sensitivity analyses.

The implementation is in `dgraudit/v2/`, the schemas are in `schemas/`, and the current Web UI is in `src/`. Formal built-in browser assets remain at their validated paths under `public/data/`.

## Quick start

Prerequisites: Python 3.9, Node.js 20 or newer, and npm. The frozen formal examples do not train a model or reselect samples/tests.

```bash
python -m pip install -r requirements.txt
npm ci

python -m dgraudit validate \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json

python -m dgraudit audit \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json \
  --output dgrainsight_session_v2.json

python -m dgraudit validate-session dgrainsight_session_v2.json
npm run dev
```

On Windows PowerShell, use backticks instead of backslashes for multiline commands, or place each command on one line.

The default audit output is Session v2. A legacy v1 session is generated only with an explicit `--session-version 1` or `--legacy-v1` request.

## Offline Audit CLI

- `python -m dgraudit validate --config ...` validates a current Config v2; legacy v1 configs retain their V01-V09 adapter preflight.
- `python -m dgraudit audit --config ... --output ...` generates Session v2 by default.
- `python -m dgraudit validate-session ...` applies the Session v2 semantic and JSON-Schema checks.
- `python -m dgraudit wizard ...` provides an interactive edge-selection workflow. Formal mode displays the frozen protocol before execution.

Two frozen current examples are provided:

- `configs/formal_audit_v2_dgraformer_etth1_frozen40.json`
- `configs/formal_audit_v2_msgnet_etth1_frozen14.json`

## Web demo

```bash
npm ci
npm run dev
```

The built-in demo loads current Session v2 assets for DGraFormer and MSGNet. The import panel accepts validated Session v2 files and explicitly labeled legacy Session v1 files. A v1 import supports graph and descriptive case inspection only; its single-case empirical inference is never presented as current cross-sample evidence.

Production build:

```bash
npm run build
```

GitHub Pages deployment remains defined by `.github/workflows/deploy.yml` and `vite.config.ts`; repository cleanup does not change the base path or asset URLs.

## Method in brief

DGraInsight evaluates learned graph relations by:

1. performing real graph interventions;
2. comparing the focal intervention with unique matched alternatives;
3. computing per-sample/test excess response `D`;
4. aggregating evidence across predeclared audit units;
5. applying dependence-appropriate inference;
6. correcting within frozen hypothesis families.

See `docs/AUDIT_SESSION_V2.md`, `docs/REPRODUCIBILITY.md`, and `schemas/dgrainsight_audit_session_v2.schema.json` for the full current contract.

## Repository map

| Path | Role |
|---|---|
| `dgraudit/v2/` | Current formal pipeline, dependence/inference/family logic and Session v2 writer |
| `dgraudit/adapters.py` | Shared frozen DGraFormer/MSGNet/MTGNN adapter layer |
| `schemas/` | Current v2 and explicitly retained v1 schemas |
| `configs/formal_audit_v2_*.json` | Frozen current Config v2 examples |
| `src/` | Current Web v2 plus explicit v1 import compatibility |
| `public/data/` | Current built-in Web assets and protected graph/sample data |
| `tests/fixtures/` | Frozen graph/statistical regression fixtures |
| `artifacts/cross_sample_validation/` | Current DGraFormer frozen statistical inputs |
| `artifacts/msgnet_cross_test_v1/` | Historical-named raw 14-test fixture used by current v2 aggregation |
| `legacy/v1/` | Legacy explanation and isolated historical materials |

The complete publication classification is in `DGRAINSIGHT_REPOSITORY_CLASSIFICATION.md`.

## Reproducibility

Follow `docs/REPRODUCIBILITY.md`. It records tested versions, frozen configs, expected p/q/family/support regressions, required public fixtures, and how to supply external datasets/checkpoints.

Run the public regression gate:

```bash
python -m unittest discover -s tests -p "test_*.py"
npm run test:web-session-v2
npm run test:session-validator
npm run test:web-graph-regression
npm run build
```

## External data and checkpoints

Raw third-party datasets, local checkpoints, and upstream model source trees are not automatically redistributable and are not bundled merely for convenience. Public configs use logical paths. For a local live-model audit, obtain the model and data from their official sources, place them outside the repository (the examples use `../external/`), and verify the documented SHA-256 before use.

The frozen built-in sessions contain derived model outputs required by the Web demo; they do not grant a new license for upstream source code, datasets, or checkpoints.

## Legacy compatibility

Session v1 used single-case empirical inference and legacy case-level BH. It is not the statistical method used for current formal results. Old Session v1 files can still be imported for graph and descriptive case inspection.

See `legacy/v1/README.md`. Use Session v2 for all current formal evidence.

## License and citation status

This repository does not yet contain an owner-approved `LICENSE` or verified `CITATION.cff`. That is a release blocker: absence of a license does not grant reuse rights. The project owner must choose the source license and provide final citation metadata before public upload approval.

