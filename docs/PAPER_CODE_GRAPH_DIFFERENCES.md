# Paper, code, and website graph-stage differences

## Executed model code

The supplied checkpoint executes `Graph_constructor.forward` in `layers/DGraFormer_framework.py`. For each of seven windows it computes:

1. learned node embeddings after linear layers and `tanh`;
2. a blend of the static cosine prior and the learned matrix;
3. `ReLU(tanh(...))` activation;
4. diagonal removal;
5. global Top-K over all `N × N` slots with `K = floor(N × N × w_ratio)`;
6. self-loop addition;
7. row normalization.

## Important implementation details

- Top-K is computed over all `N × N` flattened positions after the diagonal has been set to zero. It is not explicitly restricted to off-diagonal candidates.
- `w_ratio=0.5`; this differs from the website exporter's additional fixed 40% selection.
- The returned adjacency is already self-looped and row-normalized.
- The blend proportion is `min(current_epoch / 5, alpha)`, with `alpha=0.9`. Saved `adjs.npy` files were generated with `current_epoch=71`, so the effective blend proportion is 0.9.
- Graph parameters are window-specific but not sample-conditioned. The sample time indices select among seven precomputed window matrices.

## Website mismatch

The old website exporter writes the same final normalized matrix into both `static_graph` and `dynamic_graph`, then performs another 40% Top-K to create `sparse_graph`. Those fields must not be presented as the model's true graph stages.

Phase 2 artifacts now preserve each real intermediate tensor separately. No causal or importance claim follows from these matrices.
