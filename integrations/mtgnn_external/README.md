# External MTGNN Adapter — Quick Start

This module connects public MTGNN code to DGraInsight through the external `custom` adapter route.
It produces a Portable Audit Session v2 JSON that can be imported into the website.

## What you need

- MTGNN source containing `net.py` and `util.py`;
- a checkpoint whose architecture matches the config;
- a comma-delimited numeric dataset without a header or date column;
- one Config v2 file.

Start from:

```text
configs/custom_adapter_mtgnn_exchange.json
```

Update these config fields for your run:

```text
checkpoint.path and checkpoint.sha256
dataset.path, dataset.sha256 and dataset.variables
adapter_config.model_source_root
adapter_config.model.*
```

`dataset.variables`, the number of data columns, and `model.num_nodes` must match. Model parameters
must also match the checkpoint used during training.

## Generate the JSON

Run from the DGraInsight repository root.

### 1. Validate

```powershell
python -m dgraudit validate-adapter `
  --config configs\custom_adapter_mtgnn_exchange.json
```

Continue only when V01–V09 pass and the report says:

```text
Quick Inspection readiness: READY
```

### 2. Select a real learned edge and run the audit

```powershell
python -m dgraudit wizard `
  --config configs\custom_adapter_mtgnn_exchange.json `
  --sample 0 `
  --limit 10 `
  --output outputs\mtgnn_session_v2.json
```

The wizard displays real retained edges from the MTGNN learned graph. Enter an edge number and
confirm the audit. It writes:

```text
outputs/mtgnn_session_v2.json
```

### 3. Import into the website

```powershell
npm run dev
```

Open the local website, click **Choose DGraInsight Session**, and select:

```text
outputs/mtgnn_session_v2.json
```

The JSON contains the full learned graph for context, but one selected relation is the Quick
Inspection target. The remaining eligible edge removals are stored as matched controls. The website
shows the locked audited edge, prediction replay, magnified prediction change, control distribution,
`D`, graph metadata and provenance.

## If you change the data

Use a checkpoint trained for that data and update the dataset path/hash, node labels, `num_nodes`,
sequence settings, horizon, normalization and split ratios. Then validate and run the wizard again.

## If validation fails

Run with bounded debug details:

```powershell
python -m dgraudit validate-adapter `
  --config configs\custom_adapter_mtgnn_exchange.json `
  --debug
```

Do not edit `OFFICIAL_ADAPTER_REGISTRY`; this module is intentionally loaded only through
`adapter: "custom"`.
