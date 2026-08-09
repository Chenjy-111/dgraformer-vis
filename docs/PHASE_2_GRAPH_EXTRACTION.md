# Phase 2 Real Dynamic-Graph Extraction

## Result

All seven graph windows were extracted for ETTh1, ETTh2, ETTm1, ETTm2, and Weather directly from the loaded checkpoint parameters. Each record preserves the static prior, blended raw score, activated score, diagonal-removed score, model Top-K mask, Top-K graph, self-loop graph, and final row-normalized graph.

The final normalized matrices were compared with the supplied `adjs.npy` files using `torch.testing.assert_close(atol=1e-6, rtol=1e-5)`.

## Aggregate validation

- Datasets: 5
- Windows per dataset: 7
- Total window traces: 35
- ETTh1 final maximum absolute difference: `5.960464477539063e-08`
- ETTh2, ETTm1, ETTm2, Weather final maximum absolute difference: `0.0`
- Removed-diagonal maximum absolute value: `0.0`
- Maximum normalized row-sum error: `1.1920928955078125e-07`
- All normalized values finite: yes
- ETT Top-K mask slots per window: 24 of 49
- Weather Top-K mask slots per window: 220 of 441

## Reproduction

- Run ID: `bc60c5a9f09c46d5e176a2e014bb7b516c7c562270f86c31bb382ee48342175b`
- Manifest: `artifacts/runs/<run_id>/manifest.json`
- Per-dataset raw stage tensors: `artifacts/runs/<run_id>/graphs/*.json`
- Command: `artifacts/runs/<run_id>/command.txt`
- Environment: `artifacts/runs/<run_id>/environment.json`
- Logs: `artifacts/runs/<run_id>/stdout.log`, `stderr.log`

## Scientific boundary

These artifacts establish graph-stage provenance and numerical agreement with the supplied final matrices. They do not establish that a retained edge is important, causal, stable across training runs, or influential to a prediction. Those questions require later discovery and intervention phases.
