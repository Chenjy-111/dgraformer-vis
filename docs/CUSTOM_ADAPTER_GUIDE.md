# Custom Adapter Guide

## 1. Who should use this guide

Use this guide when you own or can run the source code of a learned-graph forecasting model
and need DGraInsight Quick Inspection without adding the model to the official registry.
DGraInsight does not infer an architecture from a checkpoint.

## 2. Eligible models

The current audit object is a graph learned by, and actually used during, prediction. The graph
must be extractable, replaceable in the real forward path, and have stable variable/node relation
identity. Dynamic graphs, multi-scale graphs, and learned global adjacency can qualify.

A network without a learned graph, a model whose only graph is fixed and outside the learned
result, or a model whose internal graph cannot be overridden does not satisfy this contract.
Visual-only similarity matrices are not audit graphs.

## 3. Required files

Prepare all five inputs locally:

1. Model source code.
2. Exact model configuration.
3. Exact checkpoint.
4. Dataset and real sample preprocessing.
5. A `DynamicGraphForecastAdapter` implementation.

The browser accepts only Session v2. It never imports Python or runs a checkpoint.

## 4. Adapter contract

Copy `dgraudit/examples/custom_adapter_template.py`. Keep the six method signatures:

- `load_checkpoint`: initialize/load exact state, device and eval mode; reject incompatible state.
- `load_sample`: execute native preprocessing for the exact split index and return all replay inputs.
- `predict`: execute a real checkpoint-backed forward returning `[1, pred_len, node_count]`.
- `extract_graph_stages`: return one or more canonical `GraphContext` values containing the graph
  actually consumed by the prediction path.
- `predict_with_graph_override`: inject the supplied graph at that consumption point and re-run the
  real forward.
- `get_metadata`: return technical model, adapter, dataset, node and context identity.

`close()` is optional cleanup. `from_audit_config(config, resolved_paths)` is the explicit stable
construction hook; the base implementation calls `__init__(config, resolved_paths)`.

For native datasets that are not date-column CSV files, override the optional class method
`validate_dataset_file(dataset_path, dataset_config)`. Validate the original NPZ/text/pickle format
and node order directly; do not create a cosmetically compatible CSV that bypasses native
preprocessing. Returning `None` retains the strict default CSV validator.

Declare technical capabilities with `AdapterCapabilities`. Capabilities never declare statistical
validity and contain no `supports_formal_audit` flag.

## 5. Step-by-step implementation

Set stable `ADAPTER_ID`, `MODEL_NAME`, and, only when reliable, `ADAPTER_VERSION`. Declare the native
context type, audit graph tensor name, dataset formats, multi-context behavior and whether a broader
override is technically implemented. Then implement real model construction, checkpoint load and
sample preprocessing before graph methods.

The deterministic test-only reference is `tests/fixtures/custom_adapter/tiny_custom_adapter.py`.
It proves the loading mechanism and shared core; it is not a fourth official model or benchmark.

## 6. Graph extraction requirements

Each returned `GraphContext` has:

- a stable `context_id`, `context_type`, and integer `index`;
- `audit_graph`, a finite `[node_count, node_count]` numeric operand;
- optional additional `graphs`, `display_label`, technical `metadata`, and identity fields.

Node order must exactly match `dataset.variables`. The audit graph must be the tensor used for the
current prediction computation, not a detached visualization that does not affect forward.

## 7. Intervention requirements

`predict_with_graph_override` must accept `identity` and `structural_edge_removal`. The override
contains the exact learned graph selected by the core plus native context and relation identity.
Inject it into the real model path, re-run prediction, and return:

```python
{
    "prediction": real_prediction,
    "graph_before": original_graph,
    "graph_after": injected_graph,
    "protocol": bounded_technical_protocol,
}
```

Do not mutate only the exported graph copy. Zero intervention response is valid negative evidence;
it is not a reason to fabricate an effect or fail conformance.

## 8. Identity override validation

The validator injects the original graph unchanged and compares the replay against baseline with
the existing tolerances `atol=1e-6`, `rtol=1e-5`. A mismatch fails conformance because subsequent
removals cannot be interpreted as graph-only replays.

## 9. Run adapter validation

Use explicit Config v2 fields:

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

The loader imports only the named module/class from the explicit source root, verifies the
`DynamicGraphForecastAdapter` subtype and abstract-method completeness, then runs V01–V09:

```bash
python -m dgraudit validate-adapter --config configs/my_custom_quick.json --debug
```

No machine-wide scan occurs and no failure falls back to an official adapter. Python import is
local/offline code execution; review custom adapter code before opting in.

## 10. Run Quick Inspection

Inspect real retained relations, then audit one declared relation:

```bash
python -m dgraudit edges --config configs/my_custom_quick.json
python -m dgraudit audit --config configs/my_custom_quick.json --output dgrainsight_session_v2.json
```

The shared core performs focal removal and all unique eligible directed non-self removals in the
same scope as matched controls. It computes case evidence and `D = focal - control mean` from real
forwards. It does not compute a single-case p/q value.

## 11. Export Session v2

The same Session v2 writer and validators are used for official and custom adapters:

```bash
python -m dgraudit validate-session dgrainsight_session_v2.json
```

No `CustomModelSession` schema exists. Provenance records module/class/version where available and
actual config, dataset and checkpoint hashes. Unavailable identity remains unavailable; it is never
replaced by a random hash.

## 12. Import into the Web UI

Run `npm run dev`, choose the generated JSON in the Audit Session area, and inspect the generic
imported workspace. Unknown context types are shown as generic graph contexts; the UI does not
pretend they are windows or scales. Browser import validates stored evidence and performs no model
execution, intervention, statistics or scientific inference.

## 13. Formal Audit requirements

Adapter conformance enables technical Quick Inspection readiness only. Formal Evidence Audit also
requires a separately declared and validated protocol: frozen samples, candidate family, exact
context identity, intervention scopes, unique control rules, primary inference, dependence handling,
multiplicity correction and sensitivity protocol. Custom adapter conformance does not create these
scientific declarations and therefore does not automatically enable the formal CLI.

## 14. Common failures

- `Custom adapter module could not be imported`: module/source root is wrong or import dependencies
  are missing; use `--debug` for the bounded underlying exception.
- `Adapter class not found`: class name is not exported by the module.
- `Adapter does not satisfy ... type requirements`: inherit `DynamicGraphForecastAdapter`.
- `Adapter contract incomplete`: implement every abstract method.
- `Graph extraction failed`: return non-empty canonical contexts and a finite square audit graph.
- `Identity mismatch`: the override path differs from baseline computation.
- `Adapter metadata incomplete`: supply stable model/dataset/node/context technical identity.
- `Relation not present`: select a retained directed edge shown by `dgraudit edges`.

## 15. Scientific limitations

Passing conformance does not establish model quality, checkpoint authenticity, graph importance,
causality, formal evidence, statistical support, or a paper conclusion. DGraInsight audits functional
response inside the exact executed model/protocol. Claims must stay within that boundary.
