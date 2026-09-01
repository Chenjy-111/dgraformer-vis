# DGraInsight Custom Adapter Guide

DGraInsight can audit additional learned-graph forecasting architectures through an explicit,
local-only adapter contract. It does not infer an architecture from a checkpoint.

Required local inputs are model source, model configuration, exact checkpoint, dataset with native
preprocessing, and a `DynamicGraphForecastAdapter`. Copy
`dgraudit/examples/custom_adapter_template.py` from the repository and implement:

- `load_checkpoint`
- `load_sample`
- `predict`
- `extract_graph_stages`
- `predict_with_graph_override`
- `get_metadata`

Native non-CSV integrations may also override `validate_dataset_file` to validate the original
dataset format and node order without converting or fabricating an intermediate CSV.

The extracted graph must be the learned graph actually used by prediction, with stable node and
context identity. The override must inject the supplied graph into the real forward path. Identity
replay must match baseline under the declared tolerance; relation removal only needs to complete
with a finite real prediction, and a zero response is valid.

Declare the integration explicitly in Quick Inspection Config v2:

```json
{
  "adapter": "custom",
  "custom_adapter": {
    "module": "my_adapter_module",
    "class": "MyGraphAdapter"
  },
  "source_root": "/local/model/source"
}
```

Then run offline:

```bash
python -m dgraudit validate-adapter --config configs/my_custom_quick.json
python -m dgraudit edges --config configs/my_custom_quick.json
python -m dgraudit audit --config configs/my_custom_quick.json --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```

Import the resulting Session v2 into the Web UI. The browser reads and validates the portable
session; it never executes Python, a checkpoint, an intervention, or statistics.

Passing adapter conformance means only that technical model loading, graph extraction and graph
override are executable. It does not establish model validity, checkpoint authenticity, relation
importance, causality, formal evidence, statistical support, or a scientific conclusion. Formal
Evidence Audit additionally requires a separately declared and validated protocol with frozen
samples, candidates, scopes, controls, inference, dependence and multiplicity rules.

See `docs/CUSTOM_ADAPTER_GUIDE.md` in the repository for the complete implementation guide and
failure reference.
