# MSGNet integration status

## Scope

The first integration target is MSGNet on ETTh1 with lookback 96 and prediction length 96. It reuses the five audited website test indices: `0`, `537`, `1074`, `1611`, and `2148`.

The website will continue to consume precomputed, auditable artifacts. It will not claim browser-side model inference.

## Source and current inputs

- Supplied source tree: `C:/Users/cj/Desktop/MSGNet-main`
- Upstream repository: `https://github.com/YoZhibo/MSGNet`
- Source Git metadata: missing from the supplied tree; individual source hashes are recorded by preflight.
- ETTh1 input: reused from the audited DGraFormer source tree.
- ETTh1 SHA-256: `f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066`
- MSGNet checkpoint: currently missing.

## Verified architecture semantics

Each MSGNet `ScaleGraphBlock` selects `top_k` periods from the current batch using FFT amplitudes. It also owns `top_k` graph modules. Each graph module constructs a parameterized adjacency as:

```text
softmax(relu(nodevec1 @ nodevec2), row dimension)
```

The adjacency is passed into MixHop propagation, which adds self-loops and row-normalizes it internally. Consequently:

- scale selection and scale aggregation weights are input-conditioned;
- the adjacency of each graph module is checkpoint-parameterized rather than generated directly from each sample;
- the appropriate website term is `scale-conditioned adaptive relation graph`, not `per-sample dynamic graph`;
- an edge intervention must occur before MixHop adds self-loops and normalizes the graph.

### Sequential scale-path caveat

The supplied implementation updates `x` inside the scale loop (`x = self.gconv[i](x)`). The graph-convolution branches are therefore not functionally independent parallel branches: the input of a later scale includes preceding graph updates, and the residual after scale aggregation also uses the last updated `x`.

Consequently, a very small final softmax scale contribution does **not** prove that the corresponding graph module has negligible functional influence. The website must display scale contribution and measured edge-removal impact as separate quantities.

## Data alignment

MSGNet and DGraFormer use the same ETT hourly split boundaries. With identical lookback and prediction lengths, equal test indices address equal raw timestamp ranges. `audit_msgnet_preflight.py` records those ranges rather than relying on the index assumption alone.

Run the dependency-free preflight with:

```text
python dgraudit/cli/audit_msgnet_preflight.py --config configs/msgnet_etth1.json --output artifacts/msgnet_preflight
```

## Current gate

Phase 1 baseline execution is blocked until a real MSGNet checkpoint and a Python environment containing the required PyTorch stack are available. No MSGNet prediction, graph, or edge-impact value is currently claimed.

## Next implementation steps

1. Install or select a compatible PyTorch environment.
2. Train MSGNet from the recorded ETTh1 configuration, or register a configuration-matched official checkpoint.
3. Add a `MSGNetAdapter` without modifying the upstream default forward path.
4. Reproduce five single-sample baseline predictions and save manifests, arrays, metrics, logs, and hashes.
5. Instrument graph extraction and prove identity graph replay before implementing edge removal.
