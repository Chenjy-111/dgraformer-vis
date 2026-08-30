# DGraInsight reproducibility guide

This guide reproduces the current Session v2 audit and Web display without retraining a model, reselecting samples/tests, or changing the frozen statistical protocol.

## 1. Environment

The frozen migration was verified with Python 3.9.13, NumPy 1.24.3, PyTorch 2.1.1, Node.js 24, and the dependency lock in `package-lock.json`. Python 3.9 is the reference environment for the complete adapter test suite.

```bash
python --version
node --version
npm --version
```

## 2. Installation

```bash
python -m venv .venv
```

Activate the environment, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
npm ci
```

For GPU-backed live-model validation, install the PyTorch build matching the local CUDA runtime according to the official PyTorch instructions. Frozen Session v2 reproduction itself must not train a model.

## 3. Repository structure

- `dgraudit/v2/`: current Config v2, controls, dependence, inference, family correction and session logic.
- `schemas/`: current v2 schemas plus the retained v1 compatibility schema.
- `configs/formal_audit_v2_*.json`: public frozen formal examples.
- `artifacts/cross_sample_validation/`: DGraFormer frozen candidate-level inputs.
- `artifacts/msgnet_cross_test_v1/`: MSGNet frozen raw 14-test inputs (historical name, current v2 aggregation input).
- `artifacts/sessions/`: v1 graph-core migration fixtures; never fetched by production Web v2.
- `public/data/`: built-in browser assets.
- `tests/fixtures/`: protected graph baselines.
- `legacy/v1/`: compatibility documentation and isolated historical materials.

## 4. Dataset preparation

Live-model audits require the official dataset outside this repository. The ETTh1 bytes used for the frozen evidence have SHA-256:

```text
f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066
```

Place a licensed copy at a path such as `../external/data/ETTh1.csv`, then update a local copy of the relevant config. Do not commit personal absolute paths or raw data without confirmed redistribution rights.

## 5. Checkpoint preparation

Live DGraFormer/MSGNet/MTGNN audits require their official upstream source tree and a compatible checkpoint. Store these outside the repository, for example under `../external/<model>/`. Record the logical filename and SHA-256. Do not commit local `.pt`, `.pth`, or checkpoint directories unless the owner has confirmed both license and distribution method.

The frozen DGraFormer checkpoint hash is:

```text
f6abbd4e9b32ae80851f42d5476069c41c66b900b181f9f24c56d445a1cead9f
```

## 6. Audit Config v2 examples

Current public examples:

- `configs/formal_audit_v2_dgraformer_etth1_frozen40.json`
- `configs/formal_audit_v2_msgnet_etth1_frozen14.json`

They freeze sample/test units, candidates, unique-control rules, dependence class, primary inference, BH families, alpha and sensitivity settings before aggregation.

## 7. CLI validation

```bash
python -m dgraudit validate \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json
```

Expected status: `ready_for_audit`, with V10 and V11 passing. Legacy v1 configs continue to invoke the V01-V09 adapter preflight.

## 8. Formal audit

```bash
python -m dgraudit audit \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json \
  --output dgrainsight_session_v2.json
```

This reads frozen, predeclared inputs and regenerates formal aggregation. It does not train a model, change controls, or select results by p-value.

MSGNet reproduction uses the corresponding frozen14 config. Its embedded intervention trajectories make the output substantially larger.

## 9. Session v2 output

Validate the result in Python:

```bash
python -m dgraudit validate-session dgrainsight_session_v2.json
```

The schema is `schemas/dgrainsight_audit_session_v2.schema.json`. Case evidence is descriptive; candidate-level p/q is stored only in `cross_sample_evidence` and its frozen `hypothesis_families`.

## 10. Browser import

```bash
npm run dev
```

Open the import panel, choose the generated JSON, and verify that it is identified as Session v2. The browser validates and displays the offline result; it does not rerun the model, construct a hypothesis family, or recompute p/q.

## 11. Built-in demo

The built-in demo loads:

- `public/data/evidence/dgraformer_etth1_session_v2.json`
- `public/data/evidence/msgnet_etth1_session_v2.json`
- `public/data/models/msgnet/etth1/graph_catalog_v2.json`

The default UI must not fetch legacy empirical-p/BH catalogs.

## 12. Expected regression tests

```bash
python -m unittest discover -s tests -p "test_*.py"
npm run test:web-session-v2
npm run test:session-validator
npm run test:web-graph-regression
npm run build
```

The graph regression must pass for DGraFormer, MSGNet and MTGNN. Frozen statistical expectations include:

- DGraFormer W6 `0→4`: p `0.0010998900109989002`, q `0.008799120087991202`.
- DGraFormer all-retained `0→2`: p `0.00009999000099990002`, q `0.00039996000399960006`.
- MSGNet family sizes: 126 single-scale and 42 all-scale.
- MSGNet supported counts: 27 and 14.

These are regression expectations, not production hardcodes.

## 13. Statistical protocol summary

For each frozen candidate, DGraInsight computes the focal intervention response minus the mean response over all unique eligible controls. Inactive units are excluded without zero imputation. DGraFormer uses the declared moving-block bootstrap for overlapping windows; MSGNet uses complete exact sign-flip enumeration for 14 non-overlapping tests. Primary BH is applied within predeclared families. Sensitivity results do not replace the primary result.

## 14. Legacy v1

Session v1 is retained only for compatibility and graph/descriptive inspection. Its single-case empirical inference and case-level BH are not current formal evidence. See `legacy/v1/README.md`.

## 15. Missing or private resources

If an upstream dataset, source tree or checkpoint is absent, the live-model path must fail clearly. Do not substitute random/mock data, a nearest case, or a different checkpoint. Record the official source, expected logical path, filename and hash. Private or license-uncertain resources belong outside Git and should be distributed only through an owner-approved release/LFS/external channel.

