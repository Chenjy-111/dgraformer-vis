# DGraInsight Adapter Contract audit

## Existing public contract

`DynamicGraphForecastAdapter` is the existing abstract model boundary. It has six abstract
methods and one optional cleanup hook:

| Method | Input | Output | Current responsibility |
|---|---|---|---|
| `load_checkpoint(checkpoint_path)` | Resolved local path string | `None` | Load the exact state on the adapter device, fail on incompatibility, switch to eval mode |
| `load_sample(split, sample_index)` | Native split and exact integer index | Mapping | Return every model-native input needed by baseline, graph extraction and replay |
| `predict(batch)` | Adapter-owned sample mapping | Array/tensor | Run a real checkpoint-backed forward; official adapters return `[1, pred_len, node_count]` |
| `extract_graph_stages(batch)` | Same sample mapping | Mapping | Return the learned graph actually used by the forward, plus model-native stages/metadata |
| `predict_with_graph_override(batch, graph_override)` | Same sample plus explicit override mapping | Mapping | Re-run the real forward and return `prediction`, `graph_before`, `graph_after`, and `protocol` |
| `get_metadata()` | None | Mapping | Return technical model/adapter/dataset/device provenance |
| `close()` | None | `None` | Optional process-state cleanup |

The abstract signatures are sufficient for an external learned-graph forecasting model.
They do not prescribe a constructor, graph context representation, or statistical protocol.

## Official implementations

### DGraFormer

- Device: the upstream `Exp_Main` device; checkpoint loaded with `map_location`, strict
  `load_state_dict` behavior, then eval mode.
- Sample: upstream dataset returns `x`, `y`, and `time_index`; the runtime adds batch axes.
- Prediction: `[1, pred_len, n_vars]` from the real model forward at the declared epoch.
- Context: `window`; extraction returns `windows`, each containing static prior, raw score,
  activated graph, diagonal-removed graph, top-k mask/graph, self-loop graph and final
  row-normalized graph.
- Audit graph: `normalized`. It is the graph returned by the graph constructor in the
  prediction path.
- Override: temporarily replaces the graph-constructor forward. Local and all-window
  structural removals are supported; structural edits are row-renormalized.
- Hidden constraints: upstream source layout and current working directory, declared epoch,
  dataset column order, and the top-k graph semantics.

### MSGNet

- Device: CUDA 0 when available, otherwise CPU; exact state dict load and eval mode.
- Sample: upstream ETTh loader returns `x`, `y`, `x_mark`, `y_mark`; decoder input is rebuilt
  exactly as the model expects.
- Prediction: `[1, pred_len, n_vars]` from the real MSGNet forward.
- Context: `scale` nested in `layer`; extraction returns raw affinity, activated affinity,
  adaptive adjacency, self-loop graph and effective normalized graph plus FFT metadata.
- Audit graph: `adaptive`, because it is the adjacency passed into the graph convolution.
- Override: temporarily replaces the selected graph-convolution forward; one scale or all
  scales in the selected layer can be changed.
- Hidden constraints: `enc_in == c_out == variable count`, `top_k` scale count, ETTh loader
  schema, and `(layer, scale_index)` as native identity.

### MTGNN

- Device: CUDA 0 when available, otherwise CPU; accepts a plain state dict or a mapping with
  `state_dict`, loads strictly, then eval mode.
- Sample: upstream `DataLoaderS` test split; normalized inputs and de-normalization scale are
  preserved.
- Prediction: `[1, pred_len, n_vars]` after restoring the dataset scale.
- Context: one `global_graph`; extraction returns the learned adjacency and its transpose.
- Audit graph: `learned_adjacency`, shared by all graph-convolution layers.
- Override: temporarily replaces the graph constructor; structural removal updates the
  forward adjacency and the transpose branch follows the resulting graph.
- Hidden constraints: test-only sample loading, model node/sequence dimensions, graph
  constructor availability, and exactly one global context.

## Cross-cutting assumptions and current error behavior

- Config v2 declares node labels and the expected prediction shape. V01–V09 validate finite
  samples, predictions and square finite graphs.
- Identity replay uses the existing `atol=1e-6`, `rtol=1e-5` tolerances.
- Relation removal is required to complete with a finite prediction; a zero response is valid.
- Official adapters currently rely on `AdapterValidationSpec` for model-specific graph and
  override semantics. Quick Inspection duplicates some of those semantics through adapter-id
  branches.
- Validation converts phase failures into stable codes and can retain the underlying exception
  class/details in debug mode. It never falls back to another adapter.

## Decision

### Must change

- Add an explicit, local-only module/class loader that verifies subclass and abstract-method
  completeness without changing the official registry.
- Add lightweight technical capabilities and a unified `GraphContext` representation for
  custom adapters.
- Move Quick Inspection model semantics behind validation-spec hooks so a fourth model does
  not require a new core adapter-name branch.
- Validate custom metadata and use the same Session v2 writer and validators.

### Recommended and included in v1

- Provide a default explicit construction hook for external adapters, author-facing error
  messages, debug measurements, a deterministic checkpoint-backed fixture, and provenance
  for adapter module/class/version where available.
- Provide an optional non-abstract `validate_dataset_file` hook for truthful validation of public
  model formats such as MTGNN's numeric matrix, while retaining the strict date-column CSV validator
  as the default.

### No change required

- The six abstract method signatures.
- Official registry names (`dgraformer`, `msgnet`, `mtgnn`).
- Session v2 schema and Web import boundary.
- Frozen Formal Evidence pipeline, candidate families, inference or BH implementation.

Passing conformance means only that model loading, graph extraction and graph intervention
are technically executable. It does not establish model validity, relation importance,
checkpoint authenticity, or formal statistical support.
