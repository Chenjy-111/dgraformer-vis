# Adding a Model to DGraInsight

Status: extension contract for architectures beyond the three official v1 adapters, updated 2026-08-30.

## 1. Extension boundary

DGraInsight provides an extension path for additional graph-based forecasting architectures. It does not automatically support an arbitrary model, checkpoint, or dataset.

Each new architecture requires model-specific integration because its checkpoint structure, preprocessing, forward API, native graph semantics, graph extraction location, and intervention location are architecture-dependent. A model is not supported merely because it can produce an adjacency matrix.

The three official reference integrations are:

- `DGraFormerAdapter`: window-level graphs and exact window/broader-window intervention.
- `MSGNetAdapter`: layer/scale graphs and exact scale/all-scale intervention.
- `MTGNNAdapter`: one global learned graph and exact directed-edge intervention.

Their different temporal semantics are preserved. A new adapter must likewise expose its real native context rather than converting it to a convenient existing type.

## 2. Adapter responsibilities

A model adapter implements the offline boundary represented by `DynamicGraphForecastAdapter` in `dgraudit/adapters.py`:

```python
load_checkpoint(checkpoint_path)
load_sample(split, sample_index)
predict(batch)
extract_graph_stages(batch)
predict_with_graph_override(batch, graph_override)
get_metadata()
close()
```

The adapter owns:

- strict checkpoint loading for documented formats;
- the official dataset loader and preprocessing;
- construction of the model's real input batch;
- baseline inference in evaluation mode;
- extraction of the real model-native graph and context metadata;
- exact conversion of a declared relation into the known intervention point;
- checkpoint replay with identity and changed graph overrides;
- model-specific metadata required for provenance;
- restoration of temporary hooks, working directories, and process state.

The shared pipeline owns candidate bookkeeping, control protocols, statistics, evidence serialization, provenance, schema validation, and Audit Session export.

## 3. Adapter prohibitions

An adapter must not:

- scan an unknown model and guess where its graph lives;
- choose a different relation when the requested one is absent;
- choose an intervention because it produces a larger effect;
- convert one native context type into another without a scientifically defined mapping;
- silently unwrap undocumented checkpoint containers;
- rename/reorder variables or infer preprocessing;
- fabricate intervention outputs, controls, statistics, or provenance;
- turn missing or unavailable evidence into zero;
- treat a statistically unsupported effect as a runtime failure.

Unknown integration details must produce an explicit validation failure or unavailable evidence.

## 4. Add the preflight integration

Add a model-specific validation spec alongside the existing specs in `dgraudit/validation.py`. It must declare:

```text
adapter_id
adapter_name
model_name
native_context_type
supported_formats
required_source_files
required_model_fields
```

It must also implement:

```text
create_adapter
prepare_batch (when needed)
validate_sample
validate_graph
identity_override
intervention_override
```

Register the spec only after all nine preflight checks are meaningful for the architecture. Do not register a stub adapter to imply support.

The exact probe must retain sample, native context, source, target, and requested scope. If any field cannot be mapped to a known hook, preflight must fail before an audit run begins.

## 5. Define the native context and graph contract

Document at least:

- context identity and ordering;
- graph stage names and tensor axes;
- node identity and variable order;
- edge direction convention;
- whether self edges exist;
- how the final graph used by the forward pass is identified;
- which intervention scopes are scientifically defined;
- how identity/no-change replay is constructed;
- official numeric tolerances.

The browser reads the model, adapter, and native context type from the session itself, so a new adapter does not require a hard-coded frontend model enum. The UI can visualize a new context through the common graph/evidence contract only when Audit Session v1 preserves its semantics without loss. Do not label a scale, layer, head, component, or latent state as a `window` merely to reuse an existing screen.

## 6. Add Audit Session export mapping

The exporter must map real offline artifacts into Audit Session v1 or a deliberately versioned successor. It must preserve:

- model, adapter, dataset, and checkpoint identity;
- sample IDs and real split indices;
- every retained native context and graph tensor;
- exact source/target relation identity;
- baseline and available intervention outputs;
- matched-control values/records and their hashes;
- stored metrics and statistics without recomputation;
- local and broader-context availability separately;
- negative evidence;
- `missing`/`null`, `unavailable`, and any model-specific not-exposed state;
- source run IDs, artifact hashes, validation report hash, commands, and limitations.

If the architecture requires fields that Audit Session v1 cannot express losslessly, add a reviewed schema version instead of placing ambiguous data into a generic field and silently dropping semantics.

## 7. Required tests before claiming support

A model should not be described as supported until it has all of the following:

1. Real supported input passes V01–V09, including baseline, graph extraction, identity replay, and exact intervention replay.
2. Missing checkpoint, incompatible checkpoint, invalid dataset, invalid sample, missing native context, graph failure, identity mismatch, and unavailable intervention fail explicitly.
3. A zero/tiny/statistically unsupported intervention remains valid negative evidence.
4. Export writes one parseable session that passes structural and semantic validation.
5. A real artifact → session JSON → imported data round trip compares every scientific field using serialization-safe equality.
6. Exact lookup never substitutes a nearby sample, context, or relation.
7. The browser imports the session, preserves native context semantics, displays provenance, and performs no neural inference or statistical recomputation.
8. Existing official adapters, built-in demos, TypeScript compilation, Python tests, and production build remain green.

Test fixtures may exercise orchestration failures, but they do not replace at least one real success-path adapter run in a compatible runtime.

## 8. Documentation and claim language

Document the new model's exact source revision, supported checkpoint format, data schema, native context, intervention scope, limitations, and tested configuration in `docs/SUPPORTED_LOCAL_AUDIT.md`.

Acceptable claim before integration is complete:

> The adapter-based design provides an extension path for this architecture.

Acceptable claim after the real preflight, round-trip, UI, and regression tests pass:

> DGraInsight includes a validated model-specific adapter for this architecture and its documented input profile.

Do not claim that DGraInsight supports arbitrary forecasting models or that users can upload any checkpoint and dataset.
