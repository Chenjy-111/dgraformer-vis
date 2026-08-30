# Legacy Session v1 compatibility

Session v1 is the historical DGraInsight portable-session format. It stores graph data and descriptive case records together with the former single-case empirical inference and case-level BH results.

It is retained for two reasons:

1. existing Session v1 files must remain readable; and
2. frozen graph-core fixtures are needed to prove that Session v2 did not alter graph tensors or baseline predictions.

Session v1 is **not** the current formal statistical method. Its single-case procedure used resampled matched controls and case-level multiple-testing correction. Current formal evidence instead aggregates a candidate relation across predeclared samples/tests, applies dependence-appropriate inference, and corrects within frozen hypothesis families.

Old Session v1 files can still be imported in the website. The UI labels them `Legacy Session v1` and permits graph and descriptive case inspection. Their empirical p/BH fields are not promoted to Session v2 evidence.

The legacy CLI is explicit:

```bash
python -m dgraudit audit --config <legacy-v1-config.json> \
  --session-version 1 --output legacy_session_v1.json
```

The v1 schema remains at `schemas/dgrainsight_audit_session_v1.schema.json`; compatibility code remains in its stable source location because moving it would increase runtime risk. Current v2 inference does not import v1 inference logic.

**Use Session v2 for all current formal evidence.** See the repository root README and `docs/REPRODUCIBILITY.md`.

