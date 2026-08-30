# MTGNN in VS Code: video demonstration

Open the repository folder in VS Code:

```text
<your-local-path>\dgraformer-vis
```

Open **Terminal → New Terminal**. Keep the terminal working directory at the repository root and use the Python environment in which `requirements.txt` was installed.

## Recommended one-command demonstration

```powershell
python -m dgraudit wizard `
  --config configs\local_audit_mtgnn_exchange.json `
  --output dgrainsight_session_v2.json
```

The wizard combines graph counting, native-context selection, ranked real-edge selection, V01–V09, audit execution, and JSON generation. The separate commands below remain useful when the video needs to explain each stage individually.

## 1. Show graph count and choose a real edge

```powershell
python -m dgraudit edges `
  --config configs\local_audit_mtgnn_exchange.json `
  --sample 0 `
  --limit 10
```

The output first states the number and type of native graphs. For this checkpoint it reports one `global_graph`, followed by 28 retained directed edges and the top candidates. Each line includes the variable names and exact `source`/`target` numbers.

Open `configs/local_audit_mtgnn_exchange.json`. Under `audit.relations[0]`, keep:

```json
"context": {"type": "global_graph", "index": 0}
```

Then replace `source` and `target` with the numbers from the selected candidate. Do not set `include_broader_context` to true: this MTGNN checkpoint already uses its single global learned graph in every GCN layer.

## 2. Validate the real inputs

```powershell
python -m dgraudit validate `
  --config configs\local_audit_mtgnn_exchange.json
```

Continue only when all V01–V09 checks show a check mark and the final line is `Status: READY FOR AUDIT`.

## 3. Generate the portable JSON

```powershell
python -m dgraudit audit `
  --config configs\local_audit_mtgnn_exchange.json `
  --output dgrainsight_session_v2.json
```

Successful output ends with `status: complete`, identifies model `MTGNN`, and writes `dgrainsight_session_v2.json` in the repository root. This JSON contains stored graphs, baseline and intervention predictions, real controls, statistics, hashes, and provenance. It does not contain or upload the checkpoint or dataset.

## 4. Start the website and import

In the same terminal:

```powershell
npm run dev
```

Open the local address printed by Vite. Under **Built-in Demo or Portable Audit Session**, choose **Import Audit Session**, then select the generated `dgrainsight_session_v2.json`. Confirm that the imported source shows `MTGNN`, `Exchange-Rate`, `MTGNNAdapter`, and `global_graph`. Select the stored relation and click **Test this exact relation** to display the offline evidence.

For the narration, describe the scope as: “DGraInsight currently provides three validated official adapters—DGraFormer, MSGNet, and MTGNN—and a common portable audit protocol. Additional architectures require a model-specific adapter.”
