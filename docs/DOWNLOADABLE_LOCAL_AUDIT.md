# Downloadable DGraInsight Local Audit

DGraInsight Local Audit is a local command-line application for users who want to audit their own supported forecasting checkpoint without uploading the checkpoint, dataset, or model source.

## Fastest Windows workflow

After downloading and extracting the project, double-click:

```text
Start-DGraInsight-Audit.cmd
```

The launcher asks the user to:

1. choose DGraFormer, MSGNet, or MTGNN;
2. optionally replace the template's model-source, checkpoint, and dataset paths;
3. choose one of the detected native graph contexts;
4. choose a real retained edge by its displayed rank;
5. choose local or broader-context intervention when the architecture supports both;
6. confirm the audit.

The launcher uses the bundled Python runtime when present. Otherwise it uses `python` or the Windows `py -3` launcher from the user's existing model environment.

## Terminal workflow

Researchers can run the same workflow directly:

```powershell
python -m dgraudit wizard --config configs/local_audit_mtgnn_exchange.json
```

Paths can be supplied without editing JSON:

```powershell
python -m dgraudit wizard `
  --config configs/local_audit_mtgnn_exchange.json `
  --source-root C:\models\MTGNN `
  --checkpoint C:\checkpoints\model.pt `
  --dataset C:\datasets\exchange_rate.txt `
  --output dgrainsight_session.json
```

The template still declares the model hyperparameters and preprocessing contract. Therefore a user checkpoint must match the selected template, or the user must provide a config that records the checkpoint's real training configuration.

## Outputs

The wizard preserves the template and writes two files:

```text
dgrainsight_session.audit_config.<UTC timestamp>.json
dgrainsight_session.json
```

The timestamped config records the exact local selection and absolute input paths for reproducibility. It remains on the user's computer. Only `dgrainsight_session.json` is selected in the DGraInsight website.

## Supported scope

The model-independent workflow is shared, while checkpoint loading, sample preprocessing, native graph extraction, and graph override are supplied by validated adapters. The current release includes DGraFormer window graphs, MSGNet layer/scale graphs, and the MTGNN global learned graph. Other graph forecasting architectures require an additional offline adapter. Once that adapter emits the self-describing Audit Session v1 common graph/evidence contract, users can upload its JSON to the existing website without waiting for a new frontend model enum or deployment.
