# Phase 4 Real Checkpoint Intervention

## Result

Eight intervention protocols were executed through fresh DGraFormer checkpoint forward passes on ETTh2 test sample 0. Baseline and intervention runs both used the saturated final schedule (`current_epoch=5`, 0.1 static + 0.9 learned), matching the candidate graph extraction condition.

The selected single-edge candidate was HULL → LULL (`1 → 5`) in window 0. The selected variable was MUFL (`2`). The selected repeated local edge set was `{MUFL → HULL, LULL → MULL}` in window 2.

## Protocol results

Baseline: MAE `0.2701793611`, MSE `0.1141003668`.

| Protocol | Renormalized | Mean absolute prediction change | MAE change | MSE change |
|---|---|---:|---:|---:|
| Structural edge removal | yes | 0.0016103380 | +0.0002118051 | +0.0001861453 |
| Normalized channel mask | no | 0.0010855093 | +0.0002454519 | +0.0002310053 |
| Variable outgoing removal | yes | 0.0102538923 | -0.0040561855 | -0.0017348602 |
| Variable incoming removal | yes | 0.0040807542 | +0.0003213584 | +0.0002383068 |
| Variable associated-edge removal | yes | 0.0054880502 | -0.0013657808 | -0.0005612746 |
| Input variable mask | no graph renormalization | 0.0936854780 | +0.0128494501 | +0.0082685724 |
| Candidate edge-set removal | yes | 0.0052077207 | -0.0012697577 | -0.0012668222 |
| Keep candidate edge set only | yes | 0.0103859324 | +0.0028241873 | +0.0028427392 |

Positive and negative error changes are reported as measured; neither direction is treated as a preset success condition.

## Semantics

- Structural protocols remove entries and row-renormalize the affected matrix.
- Normalized channel masking zeros the selected final normalized message channel without renormalization.
- Input masking zeros the selected variable across all 96 input steps while leaving the graph protocol unchanged.
- Every output is produced by a real checkpoint forward pass; no prediction is synthesized in the frontend.
- An identity graph override reproduced the unmodified forward bit-for-bit (`max_abs_difference=0.0`).

## Evidence

- Run ID: `0ce6faf89f74cf6e4bc67a109bd47ef190f2cd8299ec03a3eb431a88728664d0`
- Configuration: `configs/intervention.json`
- Full graph operands and per-step/per-variable effects: `artifacts/runs/<run_id>/evidence/*.json`
- Baseline, ground truth, and intervention predictions: `artifacts/runs/<run_id>/predictions/*.npy`
- Manifest, command, environment and logs: `artifacts/runs/<run_id>/`

## Scientific boundary

These values describe model-internal responses under specified graph or input interventions. They do not establish real-world causal relationships. Matched controls, empirical p-values, confidence intervals and multiple-comparison correction have not yet been performed.
