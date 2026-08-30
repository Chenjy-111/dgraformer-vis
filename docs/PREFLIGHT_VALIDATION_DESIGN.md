# DGraInsight Preflight Validation Design

Status: Phase 2 contract, with the Phase 3 preflight implementation added on 2026-08-29 and failure-gating regression coverage updated on 2026-08-30. Unit-level orchestration and failure behavior are verified; both official adapters passed the real V01–V09 success path on 2026-08-30.

## 1. Scope and scientific boundary

Preflight v1 supports exactly two registered adapters:

- `dgraformer` / `DGraFormerAdapter`, preserving window-level graph contexts.
- `msgnet` / `MSGNetAdapter`, preserving layer-and-scale graph contexts.

The validator does not discover unknown model internals, guess dataset schemas, choose a favorable relation, replace an unavailable relation, or create synthetic evidence. An unsupported adapter or incompatible input fails before an audit run directory is created.

The browser remains outside this contract. Model loading, baseline inference, graph extraction, identity replay, and intervention replay all run offline.

## 2. Phase 3 command surface

The implemented validation command matches the repository's current module-based CLI structure:

```text
python -m dgraudit.cli.validate_audit --config audit_config.json
```

The implemented `python -m dgraudit audit` command calls this same validation function before scientific execution or output creation. It proceeds only when the report status is `READY FOR AUDIT`.

`dgrainsight validate` may be added later when the Python package has an installable console entry point. Phase 3 must not add a console command that cannot be installed reliably.

Audit Config v1 is JSON. YAML is deferred because this repository currently has no Python package metadata or YAML parser dependency. This is an equivalent explicit-config interface, not a change to the validation semantics.

Exit codes:

- `0`: every required check passed; status is `READY_FOR_AUDIT`.
- `2`: an expected validation failure; status is `NOT_READY`.
- `1`: an internal validator defect or truly unclassified exception.

The `audit` command must invoke the same preflight implementation again. It must not trust an earlier report because checkpoint, dataset, source code, or config content may have changed.

## 3. Audit Config v1

Common envelope:

```json
{
  "schema_version": "dgrainsight.audit_config.v1",
  "adapter": "dgraformer",
  "source_root": "C:/path/to/DGraFormer",
  "checkpoint": {
    "path": "C:/path/to/checkpoint.pth"
  },
  "dataset": {
    "name": "ETTh1",
    "path": "C:/path/to/ETTh1.csv",
    "format": "ett_hour",
    "date_column": "date",
    "variables": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
    "features": "M",
    "target": "OT",
    "frequency": "h",
    "seq_len": 96,
    "label_len": 48,
    "pred_len": 96
  },
  "audit": {
    "split": "test",
    "samples": [0],
    "relations": [
      {
        "sample": 0,
        "context": {"type": "window", "index": 0},
        "source": 0,
        "target": 4,
        "include_broader_context": true
      }
    ]
  },
  "adapter_config": {}
}
```

Rules common to both adapters:

- Paths are explicit and resolved relative to the config file only when they are not absolute.
- `audit.samples` contains real split indices, not UI positions.
- At least one sample and one relation are required in v1.
- Every relation references a sample declared in `audit.samples`.
- `source` and `target` are explicit integer node indices and must differ.
- `context.type` must match the registered adapter. No conversion between window and scale is allowed.
- `include_broader_context` requests the adapter's existing global scope: all applicable DGraFormer windows or all MSGNet scales. It does not change the local context.
- Identity and intervention tolerances are official adapter constants in v1, not user-configurable values. This prevents a permissive config from weakening the gate.

### 3.1 DGraFormer adapter fields

`adapter_config` contains only values currently required to reconstruct the real DGraFormer model and final graph schedule:

```json
{
  "random_seed": 202501,
  "current_epoch": 5,
  "model": {
    "numpoint_win": 24,
    "w_bias": 0,
    "d_graph": 30,
    "d_gcn": 1,
    "w_ratio": 0.5,
    "mp_layers": 2,
    "predictor_dropout": 0.0,
    "patch_len": 8,
    "stride": 8,
    "revin": 1,
    "affine": 0,
    "subtract_last": 0,
    "d_model": 16,
    "n_heads": 4,
    "e_layers": 1,
    "d_ff": 128,
    "dropout": 0.05,
    "embed": "timeF",
    "activation": "gelu"
  }
}
```

The config loader maps the normalized dataset paths and dimensions to the arguments currently consumed by `DGraFormerAdapter`. It must not require a duplicated `root_path` plus `data_path` pair from the user.

`current_epoch` is mandatory because the adapter's current default is not the canonical final schedule. It must be recorded in the validation report and later Audit Session provenance.

### 3.2 MSGNet adapter fields

MSGNet uses the same common envelope, with scale context and the model fields currently consumed by `MSGNetAdapter`:

```json
{
  "random_seed": 2021,
  "model": {
    "task_name": "long_term_forecast",
    "top_k": 3,
    "enc_in": 7,
    "c_out": 7,
    "e_layers": 1,
    "d_model": 32,
    "n_heads": 8,
    "d_ff": 64,
    "conv_channel": 32,
    "skip_channel": 32,
    "node_dim": 10,
    "gcn_depth": 2,
    "propalpha": 0.3,
    "dropout": 0.1,
    "embed": "timeF",
    "individual": false
  }
}
```

An MSGNet relation context has this exact form:

```json
{"type": "scale", "layer": 0, "index": 0}
```

No temporal-window alias is accepted for MSGNet.

## 4. Adapter validation contract

The preflight orchestrator owns check ordering, report construction, fail/skip behavior, hashing, and audit gating. Model-specific helpers own dataset interpretation, batch shape rules, native graph validation, and conversion of an exact relation probe into the existing override protocol.

The existing scientific methods remain authoritative:

```text
load_checkpoint(path)
load_sample(split, sample_index)
predict(batch)
extract_graph_stages(batch)
predict_with_graph_override(batch, override)
get_metadata()
```

Phase 3 should add the smallest adapter-specific validation surface needed around them:

```text
adapter_id
model_name
native_context_type
validate_dataset(config) -> details
validate_sample(batch, config) -> details
validate_graph(extracted, probe, config) -> details
identity_override(probe, config) -> exact override mapping
intervention_override(probe, config) -> exact override mapping
```

`ValidationProbe` contains:

```text
sample_index
context_type
context_index
layer (MSGNet only)
source
target
include_broader_context
```

Probe conversion is exact. If an adapter cannot map every field to its known intervention point, it raises a validation failure. It must never choose another sample, context, source, or target.

## 5. Ordered validation checks

Each check has status `pass`, `fail`, or `not_run`. After the first failed scientific dependency, later checks are reported as `not_run` with `blocked_by` pointing to the failed check. Config parsing may report multiple independent field errors before stopping.

### V01 — Config and adapter registration

Must pass:

- JSON parses successfully.
- `schema_version` is exactly supported.
- Required common and adapter-specific fields exist and have valid primitive types.
- Adapter ID exists in the official registry.
- Relation context type matches the adapter.
- Relation samples are declared in `audit.samples`.

Must fail on unknown fields only where silent acceptance could alter scientific meaning, such as unknown context type, intervention scope, or adapter ID. Descriptive metadata may be forward-compatible later, but v1 should remain strict.

### V02 — Input existence

Must pass:

- source root is a directory.
- required model modules exist at the official locations for the selected adapter.
- dataset is a regular file.
- checkpoint is a regular file.
- config file remains readable.

On success, compute SHA-256 for config, dataset, and checkpoint for provenance. A hash mismatch against an optional declared hash is a failure, not a warning.

### V03 — Dataset compatibility

Static checks must pass:

- format is explicitly supported by the selected adapter.
- configured date column exists and timestamps can be parsed by the official loader.
- configured variable names exist in exact order.
- feature count equals the configured/model input dimension.
- numeric values required by the selected samples are finite.
- sequence, label, and prediction lengths are positive and supported.

The adapter must then instantiate and exercise its real dataset loader. A custom parser passing while the official loader fails is still a validation failure.

The validator does not rename columns, reorder variables, infer a target, infer frequency, fill missing values, or choose another split.

### V04 — Sample construction

Run for every declared audit sample, not only the first probe. This check runs before checkpoint loading so an incompatible dataset fails as early as possible.

Must pass:

- sample index is within the real selected split.
- official loader returns every adapter-required tensor/array.
- dimensions match the config and model input dimensions.
- batch values are finite.
- normalization/preprocessing completes.

Expected shapes for the current ETTh1 profiles include:

- input: `[seq_len, variables]`.
- target container: sufficient for `[label_len + pred_len, variables]` where used by the official loader.
- MSGNet time marks: aligned with encoder and decoder lengths.

The report stores observed shapes; it does not serialize full sample values.

### V05 — Checkpoint loading

Must pass:

- `torch.load` can deserialize the file with the selected device mapping.
- the object is the checkpoint structure already supported by the official adapter.
- strict `load_state_dict` succeeds.
- all required model configuration was supplied before model construction.
- model is placed in evaluation mode.

An unexpected wrapper such as `{"state_dict": ...}` is not unwrapped heuristically unless that format is explicitly added to that adapter's supported contract.

On state mismatch, report missing keys, unexpected keys, and shape mismatches up to a bounded display limit, plus total counts.

### V06 — Baseline forward

Execute a real forward pass for the first declared relation's sample after all samples pass construction.

Must pass:

- forward completes under `no_grad` and evaluation mode.
- prediction shape is `[1, pred_len, variables]` at the adapter boundary.
- every output value is finite.

Record output shape and a serialization-stable SHA-256 over dtype, shape, and contiguous prediction bytes. Do not judge baseline quality or require a particular MAE.

### V07 — Native graph extraction

Must pass common checks:

- extraction completes from the real adapter.
- at least one native context exists.
- requested exact context exists.
- node dimension equals the model input variable count.
- required matrices are square and finite.
- source and target indices are in range and are not equal.

DGraFormer-specific checks:

- context collection is `windows`.
- requested window index exists.
- final normalized graph rows sum to one within the official numerical tolerance.
- the declared local edge has positive retained weight in the requested window.
- a declared broader-context edge has positive retained weight in at least one native window.

MSGNet-specific checks:

- context collection preserves `layer` and `scale_index`.
- requested layer/scale pair exists.
- `period` is positive.
- FFT strength and scale contribution are finite.
- adaptive/effective graph matrices have the expected dimensions.

The extracted structures remain model-native. The validator must not convert MSGNet scales into temporal windows.

### V08 — Identity/no-change intervention

Build an identity override from the same exact local probe used by V09. Execute baseline and identity through the adapter's real override hook.

Must pass:

- identity replay completes.
- shape and finiteness match baseline.
- values satisfy official adapter tolerances: `atol=1e-6`, `rtol=1e-5` for v1 unless a stricter existing verified contract applies.

Record maximum absolute difference and tolerance. Do not round predictions before comparison.

### V09 — Intervention availability and replay

Build `structural_edge_removal` for the exact declared probe and execute it through the real intervention point.

Must pass:

- the hook location exists.
- the exact context and relation are addressable.
- graph-before and graph-after metadata correspond to the requested native context.
- forward completes.
- output shape equals baseline and every value is finite.

If broader context is requested, the existing model-specific broader override is also probed:

- DGraFormer: the relation is removed only from native windows where it has positive final normalized weight.
- MSGNet: the same directed relation is overridden across the declared layer's native scale graphs.

There is deliberately no requirement that intervention prediction differ from baseline by a minimum amount. A zero, tiny, or statistically unsupported response can be valid negative evidence.

## 6. Validation report schema

Machine-readable report:

```json
{
  "schema_version": "dgrainsight.adapter_validation.v1",
  "status": "ready_for_audit",
  "adapter": {
    "id": "dgraformer",
    "name": "DGraFormerAdapter",
    "model": "DGraFormer",
    "native_context_type": "window"
  },
  "dataset": {"name": "ETTh1", "sha256": "..."},
  "checkpoint": {"sha256": "..."},
  "config_sha256": "...",
  "checks": [
    {
      "id": "V01",
      "name": "config_and_adapter",
      "status": "pass",
      "code": null,
      "message": "Supported adapter and config schema validated.",
      "expected": null,
      "found": null,
      "details": {}
    }
  ],
  "probe": {
    "sample_index": 0,
    "context_type": "window",
    "context_index": 0,
    "source": 0,
    "target": 4
  },
  "measurements": {
    "baseline_shape": [1, 96, 7],
    "baseline_prediction_sha256": "...",
    "identity_max_absolute_difference": 0.0
  }
}
```

The human-readable terminal view is derived from the same report object:

```text
DGraInsight Adapter Validation

✓ Adapter: DGraFormerAdapter
✓ Input files located and hashed
✓ Dataset validated
✓ Samples constructed
✓ Checkpoint loaded
✓ Baseline forward passed
✓ Native window graph extracted
✓ Identity intervention matched baseline
✓ Exact intervention hook available

Status: READY FOR AUDIT
```

A failure includes concrete expected/found values:

```text
✗ Dataset validation failed [DATASET_COLUMNS_MISMATCH]

Expected variables:
HUFL, HULL, MUFL, MULL, LUFL, LULL, OT

Found variables:
HUFL, HULL, MUFL, MULL, LUFL, OT

Status: NOT READY
```

## 7. Stable failure codes

Config and registration:

- `CONFIG_PARSE_ERROR`
- `CONFIG_SCHEMA_UNSUPPORTED`
- `CONFIG_FIELD_MISSING`
- `CONFIG_FIELD_INVALID`
- `ADAPTER_UNSUPPORTED`
- `CONTEXT_TYPE_MISMATCH`

Inputs and dataset:

- `SOURCE_ROOT_NOT_FOUND`
- `MODEL_SOURCE_INCOMPATIBLE`
- `CHECKPOINT_NOT_FOUND`
- `DATASET_NOT_FOUND`
- `HASH_MISMATCH`
- `DATASET_FORMAT_UNSUPPORTED`
- `DATASET_COLUMNS_MISMATCH`
- `DATASET_VALUE_INVALID`
- `DATASET_LOAD_FAILED`
- `SAMPLE_OUT_OF_RANGE`
- `SAMPLE_CONSTRUCTION_FAILED`
- `SAMPLE_SHAPE_MISMATCH`
- `SAMPLE_NONFINITE`

Checkpoint and forward:

- `RUNTIME_DEPENDENCY_MISSING`
- `CHECKPOINT_DESERIALIZE_FAILED`
- `CHECKPOINT_FORMAT_UNSUPPORTED`
- `CHECKPOINT_STATE_MISMATCH`
- `BASELINE_FORWARD_FAILED`
- `BASELINE_OUTPUT_INVALID`

Graph and intervention:

- `GRAPH_EXTRACTION_FAILED`
- `GRAPH_CONTEXT_MISSING`
- `GRAPH_SHAPE_MISMATCH`
- `GRAPH_NONFINITE`
- `RELATION_OUT_OF_RANGE`
- `RELATION_NOT_PRESENT`
- `IDENTITY_FORWARD_FAILED`
- `IDENTITY_MISMATCH`
- `INTERVENTION_POINT_UNAVAILABLE`
- `INTERVENTION_FORWARD_FAILED`
- `INTERVENTION_OUTPUT_INVALID`

Internal:

- `INTERNAL_VALIDATION_ERROR`

`INTERNAL_VALIDATION_ERROR` includes the failed phase and exception class. A traceback is shown only with `--debug`. The user-facing message must not be only `Unknown error`.

## 8. Mutation, logging, and provenance rules

- Standalone validation does not create an audit run directory.
- It may write one report only when `--output` is explicitly provided.
- Audit output directories are created only after preflight returns ready.
- Adapter monkey patches must always be restored with `finally`.
- DGraFormer's process working directory must be restored after adapter use; validation must not leak a global cwd change.
- Seeds, resolved paths, hashes, device, Python version, Torch version, tolerances, exact probe, and check outcomes are recorded.
- Full checkpoint parameters, dataset rows, and predictions are not embedded in the validation report.
- The successful validation report hash is included later in Audit Session provenance.

## 9. Phase 3 acceptance tests

Success tests, when supported inputs and a working Torch environment are available:

- DGraFormer ETTh1 passes V01-V09 with a window probe.
- MSGNet ETTh1 passes V01-V09 with a layer/scale probe.
- Both broader-context probes complete when requested.

Required failure tests:

- missing checkpoint path -> `CHECKPOINT_NOT_FOUND` before model construction.
- mismatched checkpoint -> `CHECKPOINT_STATE_MISMATCH`.
- missing or reordered dataset variables -> `DATASET_COLUMNS_MISMATCH`.
- out-of-range sample -> `SAMPLE_OUT_OF_RANGE`.
- graph extraction exception -> `GRAPH_EXTRACTION_FAILED`.
- unavailable exact window/scale -> `GRAPH_CONTEXT_MISSING`.
- absent DGraFormer edge in a requested window -> `RELATION_NOT_PRESENT`.
- altered identity hook -> `IDENTITY_MISMATCH`.
- missing intervention point -> `INTERVENTION_POINT_UNAVAILABLE`.

Regression rule: an intervention replay with zero or unsupported effect still passes V09 if the exact hook ran and returned a valid output.

## 10. Current environment implication

As rechecked on 2026-08-30, the retained `dgra_env_cuda` launcher points to a removed Python 3.9.13 base interpreter, but `artifacts/preflight/python39/python.exe` is a working restored Python 3.9.13 runtime whose `_pth` loads the CUDA environment's site-packages. It directly imports NumPy 1.24.3 and PyTorch 2.1.1+cu121 with CUDA available; `artifacts/baseline_final/baseline_validation.json` records 25/25 real checkpoint-forward comparisons with zero difference. The exact ETTh1 CSV was located under the downloaded iTransformer datasets, and its SHA-256 exactly matches the immutable ETTh1 run manifests. After hash-locking both local configs to that file, DGraFormer and MSGNet each passed V01–V09 with status `READY FOR AUDIT`; the machine-readable reports are `artifacts/preflight/dgraformer_real_validation.json` and `artifacts/preflight/msgnet_real_validation.json`.
