# Phase 1 Baseline Reproduction

## Result

The supplied DGraFormer checkpoints were loaded with Python 3.9.13 and PyTorch 2.1.1+cu121. The adapter re-ran all 25 website samples across ETTh1, ETTh2, ETTm1, ETTm2, and Weather on CUDA.

`torch.testing.assert_close` passed for all 25 comparisons with `atol=1e-6` and `rtol=1e-5`.

## Aggregate values

- Samples: 25
- Passed: 25
- Maximum absolute difference: `0.0`
- Mean of per-sample mean absolute differences: `0.0`
- Run ID: `f654f2ab710e4e51f3e7086736b32b9f064ff84f1e4ae8a0053bfdc448b36de9`

The maximum absolute difference may exceed `atol` for nonzero values while still passing the specified combined absolute/relative tolerance.

## Evidence

- Configuration: `configs/phase1_registry.json`
- Adapter: `dgraudit/adapters.py::DGraFormerAdapter`
- Validation command: `dgraudit/cli/validate_baseline.py`
- Full per-sample operands and results: `artifacts/baseline_final/baseline_validation.json`
- Saved command: `artifacts/baseline_final/command.txt`

## Scientific boundary

This phase establishes numerical equivalence between the supplied saved predictions and fresh checkpoint forward passes under the recorded tolerance. It does not establish causal relationships, pattern importance, graph-stage correctness, or intervention effects.

Phase 2 may now begin. It must instrument the original graph constructor to export every graph stage without using the website exporter's extra 40% Top-K.
