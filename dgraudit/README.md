# DGraInsight audit toolkit

`dgraudit` is the offline evidence-audit toolkit used by DGraInsight. It validates a declared audit configuration, loads an exact model checkpoint through a model adapter, inspects native learned-graph relations, performs declared interventions and matched-control comparisons, and writes a Portable Audit Session v2 for validation or browser inspection.

The browser never executes this Python package. Model execution and evidence generation happen locally; the Web application only validates and renders the resulting Session v2 JSON.

## Scientific scope

DGraInsight supports two distinct workflows:

| Workflow | Purpose | Formal inference |
|---|---|---|
| Quick Inspection | Inspect one real checkpoint-backed case and compare a selected relation removal with all unique eligible controls. | Unavailable by design for a single inspected case. |
| Formal Evidence Audit | Evaluate predeclared candidate relations across frozen samples/tests using the declared dependence, inference, multiplicity, and sensitivity protocols. | Available only when the complete formal protocol validates. |

Adapter conformance establishes technical readiness for Quick Inspection. It does not authorize or imply a formal evidence claim. Results describe behavior of the named model, checkpoint, dataset, sample, graph context, relation, and intervention; they do not establish real-world causality.

## Requirements and installation

- Python 3.9
- Node.js 20 or newer for Web validation and production builds
- Local upstream model source, checkpoint, and dataset files for live Quick Inspection

From the repository root:

```bash
python -m pip install -r requirements.txt
npm ci
python -m dgraudit --help
```

Keep third-party model source, checkpoints, datasets, credentials, and generated sessions outside the repository. Config v2 files may point to those local paths.

## Supported adapters

Maintained reference adapters and their Quick Inspection templates are:

| Model | Native graph context | Config template |
|---|---|---|
| DGraFormer | Window | `configs/local_audit_dgraformer_etth1.json` |
| MSGNet | Scale | `configs/local_audit_msgnet_etth1.json` |
| MTGNN | Global learned graph | `configs/local_audit_mtgnn_exchange.json` |

Additional learned-graph forecasting models can be loaded through an explicit local module/class declaration. Start with `dgraudit/examples/custom_adapter_template.py` and follow the [Custom Adapter Guide](../docs/CUSTOM_ADAPTER_GUIDE.md).

## Quick Inspection

### 1. Prepare a Config v2 file

Copy the closest `configs/local_audit_*.json` template and set the exact local paths for:

- `source_root`
- `checkpoint`
- `dataset`
- any model-specific `adapter_config` values

Do not modify frozen formal configs to represent an unregistered local experiment.

### 2. Validate the configuration and adapter

```bash
python -m dgraudit validate --config configs/local_audit_dgraformer_etth1.json
```

For a custom adapter, run the adapter-specific gate explicitly:

```bash
python -m dgraudit validate-adapter --config configs/my_custom_quick.json
```

V01–V09 check configuration and input identity, dataset compatibility, sample construction, checkpoint loading, baseline forward execution, native graph extraction, identity intervention, and the exact intervention hook. Continue only after the applicable checks pass.

### 3. Inspect native edge candidates

```bash
python -m dgraudit edges --config configs/local_audit_dgraformer_etth1.json --limit 10
```

Optional selectors include `--sample`, `--context`, and `--layer`. Add `--json` for machine-readable output.

### 4. Generate a Session v2

Interactive selection:

```bash
python -m dgraudit wizard \
  --config configs/local_audit_dgraformer_etth1.json \
  --output dgrainsight_session_v2.json
```

Non-interactive execution of the declared audit:

```bash
python -m dgraudit audit \
  --config configs/local_audit_dgraformer_etth1.json \
  --output dgrainsight_session_v2.json
```

On Windows, `Start-DGraInsight-Audit.cmd` launches the supported guided workflow from the repository root.

### 5. Validate and inspect the result

```bash
python -m dgraudit validate-session dgrainsight_session_v2.json
```

Start the Web application with `npm run dev`, choose **DGraInsight Session**, and import the validated JSON. Import is local to the browser; the Web application does not upload the file or rerun the model.

## Frozen Formal Evidence Audit

The repository contains two declared formal examples:

```bash
python -m dgraudit validate \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json
python -m dgraudit audit \
  --config configs/formal_audit_v2_dgraformer_etth1_frozen40.json \
  --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```

MSGNet uses `configs/formal_audit_v2_msgnet_etth1_frozen14.json` with the same sequence. These examples consume repository-owned frozen operands; they do not train a model or reselect samples, tests, candidates, or hypothesis families.

Expected scientific gates are documented in [Reproducibility](../docs/REPRODUCIBILITY.md).

## Command reference

| Command | Role |
|---|---|
| `python -m dgraudit validate --config FILE` | Validate Config v2 and all applicable V01–V11 checks. |
| `python -m dgraudit validate-adapter --config FILE` | Run V01–V09 adapter conformance for Quick Inspection readiness. |
| `python -m dgraudit edges --config FILE` | List native retained edge candidates. |
| `python -m dgraudit wizard --config FILE --output FILE` | Select a native edge and generate Session v2 interactively or with selectors. |
| `python -m dgraudit audit --config FILE --output FILE` | Execute the declared offline audit and write Session v2. |
| `python -m dgraudit validate-session FILE` | Validate JSON Schema and semantic invariants of Session v2. |

Run `python -m dgraudit COMMAND --help` for all selectors and output options.

## Output contract and provenance

Portable Audit Session v2 is the only current session contract. Its schema is [`schemas/dgrainsight_audit_session_v2.schema.json`](../schemas/dgrainsight_audit_session_v2.schema.json).

A session records model, dataset and checkpoint identity; the audit plan; samples and native graph contexts; case evidence; candidate relations and frozen hypothesis families; dependence and inference metadata; validation reports; provenance; and limitations. Case evidence stores focal and eligible-control responses plus `D = focal - control mean`. Formal p/q values are permitted only in the appropriate cross-sample/test evidence.

The Python validator, JSON Schema validator, and TypeScript browser validator fail closed on malformed tensors, invalid references, duplicated controls, imputed inactive units, invalid p/q values, and case-level formal inference.

## Package map

| Path | Responsibility |
|---|---|
| `adapters.py` | Maintained DGraFormer, MSGNet, and MTGNN adapter implementations and contract. |
| `registry.py` | Explicit loader for user-provided local custom adapters. |
| `quick_audit.py` | Native Quick Inspection runtime. |
| `validation.py` | Shared validation support. |
| `v2/` | Config v2, frozen protocols, controls, dependence, inference, families, pipeline, runner, and Session v2 writer. |
| `cli/` | Public command implementations exposed through `python -m dgraudit`. |
| `examples/` | Copyable custom-adapter template. |

Repository-level supporting paths are `configs/`, `schemas/`, `artifacts/`, `integrations/`, and `tests/`.

## Verification

Run from the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py"
npm run test:web-session-v2
npm run test:web-graph-regression
npm run build
```

These gates verify the Python audit core, Session v2 contract, graph regression fixtures, Web validators, and production build. They do not perform model training.

## Troubleshooting

- **A local path fails validation:** resolve `source_root`, checkpoint, and dataset paths from the Config v2 file and verify file hashes and access permissions.
- **V01–V09 fails:** do not generate or import a session until the reported adapter/configuration gate is fixed.
- **No candidate edge is listed:** inspect the selected sample, context, layer, graph orientation, self-edge policy, and retention thresholds declared by the config.
- **Formal inference is unavailable:** expected for Quick Inspection; formal evidence requires a separately declared and validated formal protocol.
- **Session import is rejected:** run `validate-session` and regenerate with the current Session v2 writer; retired session formats are intentionally unsupported.
- **A custom model cannot load:** verify the explicit module/class declaration and follow the custom-adapter contract without modifying the official registry.

## Further documentation

- [Supported local audit adapters](../docs/SUPPORTED_LOCAL_AUDIT.md)
- [Custom Adapter Guide](../docs/CUSTOM_ADAPTER_GUIDE.md)
- [Portable Audit Session v2](../docs/AUDIT_SESSION_V2.md)
- [Reproducibility](../docs/REPRODUCIBILITY.md)
- [MTGNN external integration](../integrations/mtgnn_external/README.md)
