# Supported local audit adapters

DGraInsight currently supports DGraFormer, MSGNet, and MTGNN through Config v2 templates:

- `configs/local_audit_dgraformer_etth1.json`
- `configs/local_audit_msgnet_etth1.json`
- `configs/local_audit_mtgnn_exchange.json`

Each template must resolve a local `source_root`, checkpoint path, and dataset path. V01–V09 verify the adapter/config, inputs and hashes, dataset compatibility, sample construction, checkpoint load, baseline forward, native graph extraction, identity intervention, and exact intervention hook.

DGraFormer exposes window contexts, MSGNet exposes scale contexts, and MTGNN exposes its global learned graph. Quick Inspection selects a real retained directed edge, performs a structural removal, evaluates all other unique eligible directed non-self edges as controls, and writes Session v2. It does not claim single-case formal inference.

```bash
python -m dgraudit validate --config configs/local_audit_mtgnn_exchange.json
python -m dgraudit edges --config configs/local_audit_mtgnn_exchange.json
python -m dgraudit wizard --config configs/local_audit_mtgnn_exchange.json --output dgrainsight_session_v2.json
python -m dgraudit validate-session dgrainsight_session_v2.json
```
