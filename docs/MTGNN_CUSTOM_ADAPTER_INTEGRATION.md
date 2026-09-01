# MTGNN external custom-adapter integration

## Purpose

This integration reruns the real public MTGNN model through DGraInsight's external adapter route:

```text
unmodified MTGNN source + Exchange-Rate + exact checkpoint
        ↓
adapter: custom + explicit module/class
        ↓
V01–V09 conformance
        ↓
real baseline / learned graph / graph override / 27 controls
        ↓
Case Evidence + Session v2
        ↓
Python, JSON Schema, and TypeScript/Web validation
```

MTGNN is already an official reference adapter, so this is not evidence of a fourth architecture.
It is a controlled real-model experiment showing that the external loading contract can reproduce an
existing known-correct integration without registry changes or core specialization.

## Inputs

| Input | Location | SHA-256 |
|---|---|---|
| Public MTGNN source | `third_party/MTGNN` | `net.py`: `07d2f774df14fcc887afeb27aaa8acaff3406a76fe5e2558924112407ac8d8af` |
| Exchange-Rate data | `third_party/MTGNN/data/exchange_rate.txt` | `0127465b51e3cd3c360f8eb2be30cfd294689a2a55903eb8245aafc396626c7f` |
| Seed-42 horizon-3 checkpoint | `artifacts/mtgnn_exchange/mtgnn_exchange_h3_seed42_state_dict.pt` | `9a3d9847bb70a580ad7ed0094ebc0ee233b0e508425ecb9adae17f051e974fe7` |
| External adapter | `integrations/mtgnn_external/mtgnn_external_adapter.py` | repository source |
| Custom Config v2 | `configs/custom_adapter_mtgnn_exchange.json` | repository source |

The third-party source/data and local checkpoint follow existing repository release boundaries and
may be ignored from a public upload. Reproduction requires obtaining/verifying those exact assets.

## Independence from the official adapter

`ExternalMTGNNAdapter`:

- is loaded only as `custom_adapter.module=mtgnn_external_adapter` and
  `custom_adapter.class=ExternalMTGNNAdapter`;
- has stable `ADAPTER_ID=mtgnn_external`;
- is not present in `OFFICIAL_ADAPTER_REGISTRY`;
- does not import, inherit, instantiate, or call `dgraudit.adapters.MTGNNAdapter`;
- constructs the public `net.gtnet` directly;
- uses the public `util.DataLoaderS` preprocessing directly;
- strictly loads the exact checkpoint;
- extracts `model.gc(model.idx)`, the adjacency consumed by MTGNN forward;
- replaces `model.gc.forward` during identity/removal replay so all mixprop layers consume the
  supplied graph and its transpose.

No upstream MTGNN file is modified.

## Native dataset validation discovered by the trial

Exchange-Rate is a comma-delimited numeric matrix without a date column. The first real integration
therefore exposed a generic-contract gap: custom validation previously assumed a date-column CSV.
The base contract now has an optional, non-abstract `validate_dataset_file` hook. MTGNN validates
the original numeric matrix, finite values, row count, node count and node labels. Default CSV custom
adapters remain backward compatible.

## Complete reproduction

Run from the repository root.

### 1. Establish the official reference

```powershell
python -m dgraudit validate-adapter `
  --config configs\local_audit_mtgnn_exchange.json

python -m dgraudit audit `
  --config configs\local_audit_mtgnn_exchange.json `
  --output .tmp\mtgnn_official_session_v2.json
```

### 2. Load MTGNN only through the external contract

```powershell
python -m dgraudit validate-adapter `
  --config configs\custom_adapter_mtgnn_exchange.json `
  --debug `
  --output .tmp\mtgnn_custom_validation.json
```

Expected: V01–V09 all pass, `Quick Inspection readiness: READY`, and formal readiness explicitly
not evaluated.

### 3. Inspect the real learned graph

```powershell
python -m dgraudit edges `
  --config configs\custom_adapter_mtgnn_exchange.json `
  --sample 0 `
  --limit 10
```

For the frozen assets, one `global_graph` contains 28 retained directed edges. The declared focal
relation is `EX0 → EX6` (`source=0`, `target=6`), weight `0.999999762`.

### 4. Run complete Quick Inspection

```powershell
python -m dgraudit audit `
  --config configs\custom_adapter_mtgnn_exchange.json `
  --output .tmp\mtgnn_custom_session_v2.json
```

This executes the baseline, identity replay, focal edge removal and 27 unique eligible real control
removals. The result contains descriptive Case Evidence and explicitly no case/formal p or q value.

### 5. Validate the same Session v2 in all layers

```powershell
python -m dgraudit validate-session .tmp\mtgnn_custom_session_v2.json
npm run test:session-v2-validator
node tests\auditSessionV2Validator.mjs .tmp\mtgnn_custom_session_v2.json
```

Expected: `SESSION V2 VALID` and `TYPESCRIPT SESSION V2 VALID`.

### 6. Compare official and external computation

Use the same device rule on both paths (`auto` selects CUDA 0 when available, otherwise CPU):

```powershell
python scripts\compare_mtgnn_adapter_sessions.py `
  .tmp\mtgnn_official_session_v2.json `
  .tmp\mtgnn_custom_session_v2.json
```

The completed run measured `max_abs_diff=0` for baseline prediction, learned adjacency,
intervention prediction, all 27 control responses, focal response and D. Dataset and checkpoint
identities matched.

Cross-device CPU/CUDA comparisons can produce normal floating-point differences and must not be
presented as adapter differences. Record the actual device or use an explicitly justified tolerance.

### 7. Import into the browser

```powershell
npm run dev
```

Import `.tmp/mtgnn_custom_session_v2.json` in the Audit Session panel. Confirm:

- model `MTGNN`;
- adapter `ExternalMTGNNAdapter` / adapter id `mtgnn_external`;
- dataset `Exchange-Rate`;
- context `global_graph:0`;
- validated graph and Case Evidence;
- Quick Inspection formal inference remains not evaluated.

The automated `npm run test:web-session-v2` regression now generates and imports both the tiny
fixture Session and this real MTGNN external Session.

## What this proves—and does not prove

It proves that explicit external loading, native non-CSV validation, real public model construction,
checkpoint load, graph extraction, identity/removal overrides, matched controls, Session v2 and Web
import work on a non-fixture codebase without modifying the official registry or audit core.

It does not add a fourth architecture, validate MTGNN scientifically, establish relation importance,
or enable Formal Evidence Audit. A different public learned-graph architecture remains the stronger
next paper-level generalization test.
