# DGraInsight Offline Audit Pipeline v2

Pipeline v2 preserves the Session v1 model/graph core and adds a separate
candidate-level statistical layer. It does not reinterpret Session v1
single-case empirical p-values or case-level BH values as cross-sample evidence.

## Modes

- `quick_inspection`: one user-selected sample/edge. It may report the graph,
  intervention trajectory, unique controls, D, rank, and percentile. Its
  `formal_inference.status` is `not_evaluated`; raw p and BH q are null.
- `formal_evidence_audit`: multiple frozen test units, a frozen candidate
  family, an audited dependence structure, a predeclared registered inference
  engine, and family-level BH.

The checked-in frozen formal configs are:

- `configs/formal_audit_v2_dgraformer_etth1_frozen40.json`
- `configs/formal_audit_v2_msgnet_etth1_frozen14.json`

Run and validate:

```text
python -m dgraudit audit --config <config-v2.json> --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```

Session v1 remains readable. Creating one now requires `--session-version 1`
or `--legacy-v1`, and its inference is labeled legacy.

## Statistical separation

`case_evidence` contains descriptive intervention output and unique matched
controls. It never contains formal sample-level p/BH fields.

`cross_sample_evidence` contains the active D vector for one sample-independent
candidate identity, primary inference, family-level BH, and named sensitivity
results. Inactive positions remain null and are excluded without zero
imputation.

DGraFormer uses the frozen, dependence-aware, one-sided null-centered moving
block bootstrap on mean D (primary L=3 only for the frozen 40-position
protocol; L=2/L=4 are sensitivity checks). MSGNet uses complete one-sided exact
sign-flip enumeration on mean D for 14 frozen non-overlapping tests. MTGNN has
no frozen formal multi-test protocol and therefore remains Quick Inspection /
case evidence only unless an explicitly validated external protocol is added.

The browser may read, validate, and display v2 JSON. It must not recompute D,
raw p, BH, family membership, or any graph/model result.
