# DGraInsight Adapter Extensibility v1 Implementation Report

## Outcome

DGraInsight now supports explicit local integration of additional learned-graph forecasting models
without editing `OFFICIAL_ADAPTER_REGISTRY` or adding a model-name branch to the Quick Inspection
core. A custom adapter can pass V01–V09, execute a checkpoint-backed baseline and real graph
overrides, produce matched-control case evidence, export Session v2, and pass the same Python, JSON
Schema and TypeScript/Web validators used by official data.

## 1. Original Adapter Contract

The original `DynamicGraphForecastAdapter` contract consisted of six abstract methods:
`load_checkpoint`, `load_sample`, `predict`, `extract_graph_stages`,
`predict_with_graph_override`, and `get_metadata`, plus optional `close`. Inputs, outputs, official
shape/device/graph assumptions and hidden constraints are recorded in
`ADAPTER_CONTRACT_AUDIT.md`.

## 2. Was the Contract modified?

The six abstract method signatures were not modified. Backward-compatible class metadata was added:
`ADAPTER_ID`, `MODEL_NAME`, `ADAPTER_VERSION`, and `CAPABILITIES`. A non-abstract
`from_audit_config(config, resolved_paths)` construction hook was added so an external class has a
stable explicit instantiation path. A non-abstract `validate_dataset_file(dataset_path,
dataset_config)` hook was also added after the real MTGNN replay exposed that the strict default
date-column CSV validator cannot truthfully validate MTGNN's numeric-matrix Exchange data. Returning
`None` preserves the original default validation. Existing official constructors and method bodies
are unchanged.

## 3. Why these changes were necessary

The execution methods were already sufficient. The missing boundary was a truthful, model-agnostic
description of graph context/technical capabilities and a constructor/loading convention. The new
`AdapterCapabilities` and internal `GraphContext` provide that description without putting
statistical validity into the adapter. Model semantics used by Quick Inspection now live in adapter
validation specs rather than adapter-name branches in the audit core.

## 4. Custom Adapter loading

Quick Inspection Config v2 uses explicit opt-in:

```json
"adapter": "custom",
"custom_adapter": {"module": "my_module", "class": "MyAdapter"}
```

`dgraudit.registry.load_custom_adapter_class` imports exactly that module from the declared
`source_root`, finds exactly that class, verifies it is a concrete
`DynamicGraphForecastAdapter` subclass, validates `AdapterCapabilities` and stable adapter/model
identity, then constructs it through `from_audit_config`. It performs no module scanning, browser
execution, fallback, or monkey patch.

Stable author-facing failures cover module import, missing class, wrong type, incomplete abstract
contract, invalid capabilities/identity and construction failure. `--debug` retains bounded
underlying exception details.

## 5. Avoiding official registry modification

`OFFICIAL_ADAPTER_REGISTRY` remains exactly keyed by `dgraformer`, `msgnet`, and `mtgnn`. The
resolver returns an official spec for those stable names; only the explicit `adapter=custom` sentinel
creates an ephemeral `CustomAdapterValidationSpec`. Users neither fork nor edit registry source.

## 6. Conformance validator coverage

`python -m dgraudit validate-adapter --config ...` runs the existing V01–V09 tolerance and failure
framework with custom support:

1. Config, explicit import, subtype and concrete contract.
2. Source/dataset/checkpoint existence and exact hashes.
3. Dataset schema and node order.
4. Exact sample construction and finite shapes.
5. Checkpoint load plus reproducible metadata.
6. Finite baseline forward with `[1, pred_len, node_count]` shape.
7. At least one unique valid graph context, finite square audit graph and valid retained relation.
8. Identity override equivalence.
9. Real relation-removal forward, finite output, graph-before/after and exact relation protocol.

The terminal report declares only `Quick Inspection readiness: READY`. Formal readiness is explicitly
not evaluated.

## 7. Identity override validation

The validator takes the exact audit graph extracted for the declared context and supplies it
unchanged to `predict_with_graph_override(type="identity")`. The replay prediction is compared with
the real baseline using the pre-existing tolerances `atol=1e-6`, `rtol=1e-5`. The deterministic
fixture measured a maximum absolute difference of `0.0`.

## 8. How the fixture proves common-core reuse

`tests/fixtures/custom_adapter/TinyDeterministicGraphAdapter` is loaded only through its configured
module/class. Its JSON checkpoint contains a fixed learned adjacency and output parameter; its CPU
forward multiplies the exact sample by that graph. Structural removal changes that same operand,
renormalizes it according to the fixture's declared semantics, and re-runs the forward.

The fixture produced one focal replay and five unique eligible directed non-self control replays,
case evidence and `D`, then Session v2. Tests assert that `dgraudit/quick_audit.py`,
`dgraudit/v2/quick.py`, and `dgraudit/edge_discovery.py` contain neither fixture identity nor an
`adapter_id == ...` model dispatch. The fixture is not in the official registry, demo catalog, paper
benchmark or formal pipeline.

## 9. Quick Inspection real-forward status

Yes. Baseline, identity, focal and every control prediction are computed by the checkpoint-backed
fixture forward. No fake/cached prediction, random adjacency, random evidence or fabricated effect is
used. The fixture baseline prediction hash was
`143b3c92893d80d13aa2f5f7db9c0b2a8d98303c885b6d037d1077eaf2d2eb47` during conformance.

## 10. Custom Session v2 validation

Yes. The generated custom Session passed:

- `validate_audit_session_v2` (the same semantic validator),
- `schemas/dgrainsight_audit_session_v2.schema.json` (the same JSON Schema),
- `validateAuditSessionV2` compiled from the Web TypeScript source.

The automated Web regression imports the offline-generated custom Session and confirms generic
context, matched controls and unavailable formal inference for both the deterministic fixture and
the real external MTGNN integration.

## 10A. Real public MTGNN external-adapter replay

MTGNN was independently re-integrated through `adapter: "custom"` in
`integrations/mtgnn_external/mtgnn_external_adapter.py`. The external class directly constructs the
public MTGNN `net.gtnet`, uses `util.DataLoaderS`, loads the real Exchange checkpoint strictly and
patches the actual graph constructor during intervention. It does not import, subclass or call the
official `dgraudit.adapters.MTGNNAdapter`, and `mtgnn_external` is not an official registry key.

The full run passed V01–V09, discovered one global learned graph with 28 retained edges, selected
`EX0 -> EX6` as the focal relation, executed the focal removal plus 27 unique real control removals,
and exported a Session v2 accepted by the Python semantic validator, JSON Schema and TypeScript/Web
validator. On the same device, the official and external-custom paths were numerically identical:
baseline prediction, learned adjacency, focal intervention, every control replay, focal response and
`D` all had maximum absolute difference `0.0`. Input source, dataset and checkpoint SHA-256 identities
are recorded in `docs/MTGNN_CUSTOM_ADAPTER_INTEGRATION.md`.

## 11. Why Formal Audit was not automatically opened

The adapter states how to execute a model. It cannot declare planned units, a frozen candidate
family, hypothesis identity, dependence, primary inference, BH family or sensitivity protocol.
Accordingly, custom conformance enables Quick Inspection only. The formal CLI fails closed for
`adapter=custom` with a separate-protocol explanation. The next safe design boundary is recorded in
`FORMAL_PROTOCOL_EXTENSIBILITY_ROADMAP.md`.

## 12. Session v2 schema changes

None. `schemas/dgrainsight_audit_session_v2.schema.json`, Python semantic rules and TypeScript import
shape were not relaxed or forked. Custom adapter module/class/version provenance uses existing open
model/provenance objects. Session v2 remains the only portable Web interface.

## 13. Formal statistical data changes

None. No frozen evidence JSON, formal operand, statistical method, inference setting, BH family,
raw-p, adjusted-q, support status or sensitivity record was modified. Pre/post frozen asset SHA-256
values are identical to `ADAPTER_EXTENSIBILITY_BASELINE.md`.

## 14. Official adapter regression

- Official registry names remain `dgraformer`, `msgnet`, `mtgnn`.
- Existing official adapter execution method bodies are unchanged; capability manifests are
  declarative additions.
- The exact graph-core regression for DGraFormer, MSGNet and MTGNN passed.
- MSGNet graph-stage/MixHop normalization, DGraFormer graph-stage invariants and intervention
  normalization tests passed.
- Official frozen Session asset hashes remained byte-for-byte unchanged.

In addition to the frozen exact graph/session regressions, this workspace now contains the real
public MTGNN source, Exchange data and a trained checkpoint used for the controlled official-versus-
external replay described above. DGraFormer and MSGNet continue to use their frozen declared gates.

## 15. Formal frozen-audit regression

Both formal pipelines were re-executed and their output Sessions validated:

| Pipeline | Planned/active | Supported results | Result |
|---|---:|---:|---|
| DGraFormer frozen40 | 40/40 | 1/8 local; 1/4 all-retained | PASS |
| MSGNet frozen14 | 14/14 | 27/126 single-scale; 14/42 all-scales | PASS |

The unit suite separately verifies frozen candidate-level `D`, raw-p, adjusted-q, support and family
identity.

## 16. Tests and build

| Gate | Final result |
|---|---|
| `python -m unittest discover -s tests -v` | PASS — 43 tests |
| `npm run test:web-graph-regression` | PASS |
| `npm run test:web-session-v2` | PASS, including fixture and real MTGNN custom Session Web imports |
| Custom Session Python semantic + JSON Schema validation | PASS |
| Custom Session TypeScript/Web validation | PASS |
| DGraFormer and MSGNet formal CLI reruns + Session validation | PASS |
| `npm run build` | PASS |
| `git diff --check` | PASS (only Git CRLF conversion notices) |

Vite continues to report the pre-existing bundle-size advisory; it is not a failure and no adapter
code runs in the browser bundle.

## Required declarations

The DGraInsight audit core was not specialized for the example custom model.

Official DGraFormer, MSGNet, and MTGNN adapter behavior remains backward compatible.

Custom adapters execute real checkpoint-backed model forwards and graph overrides.

No evidence values are fabricated when required model, graph, or provenance information is unavailable.

Passing adapter conformance validation does not imply formal statistical support.

Formal Evidence Audit remains dependent on a separately declared and validated audit protocol.

Session v2 remains the common portable interface between offline audit execution and the Web Evidence UI.
