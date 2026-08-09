# Canonical schedule correction

The website and Phase 1–4 evidence now use one inference state: the final DGraFormer graph schedule, represented by `current_epoch=5` (`0.1 × static prior + 0.9 × learned graph`). In the supplied implementation the schedule saturates at epoch 5, so epoch 71 produces the same graph and is not checkpoint metadata.

No retraining was performed. Every website prediction, graph stage, and attention tensor was regenerated from the supplied trained checkpoint in the same forward path. The 25-sample independent replay matched the canonical export exactly (`max_abs_difference=0`).

Canonical run IDs:

- Export: `d40384ae455ec45e642761902f354b38649411e45cdbd5f3f98d1b3811fa5ca9`
- Baseline replay: `f654f2ab710e4e51f3e7086736b32b9f064ff84f1e4ae8a0053bfdc448b36de9`
- Graph extraction: `bc60c5a9f09c46d5e176a2e014bb7b516c7c562270f86c31bb382ee48342175b`
- Pattern discovery: `467d53169372e3120e7964f81152bee863fc5ef121b01e5413ed813c14c10a5c`
- Intervention: `0ce6faf89f74cf6e4bc67a109bd47ef190f2cd8299ec03a3eb431a88728664d0`

The earlier epoch-1/71 mixed artifacts are superseded and must not be used for claims.
