# Reproducibility

The frozen formal examples do not train models or reselect samples/tests. Use Python 3.9 with the pinned requirements and Node.js 20 or newer.

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m dgraudit audit --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
python -m dgraudit audit --config configs/formal_audit_v2_msgnet_etth1_frozen14.json --output msgnet_session_v2.json
python -m dgraudit validate-session msgnet_session_v2.json
npm run test:web-session-v2
npm run test:web-graph-regression
npm run build
```

Expected scientific gates:

- DGraFormer: 1/8 single-window and 1/4 all-retained-window candidates supported.
- MSGNet: 27/126 single-scale and 14/42 all-scale candidates supported.
- DGraFormer, MSGNet, and MTGNN graph-core hashes match `tests/fixtures/pipeline_v2_graph_baseline.json`.

Frozen inputs are `artifacts/dgraformer_frozen40/` and `artifacts/msgnet_frozen14/`. Current graph fixtures are the two built-in Session v2 assets plus `tests/fixtures/msgnet_graph_core_baseline.json` and `tests/fixtures/mtgnn_quick_session_v2.json`.

Live Quick Inspection additionally requires local upstream model source, checkpoint, and dataset files. These private/third-party inputs are not committed.
