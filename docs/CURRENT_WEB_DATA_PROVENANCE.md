# Current Web Data Provenance

## 审计结论

当前网站的 25 个样本可以追溯到 `DGraFormer-main/demo_results/<dataset>_96/` 中保存的真实推理数组。逐值对照结果：history、ground truth 和 prediction 的最大绝对差均为 0；动态图最大差为 `5.067e-7`，来自导出时保留六位小数；注意力均值最大差为 `3.73e-8`。

因此，当前网页曲线和注意力数值可以认定为保存的真实运行结果的静态导出。该结论不等于“已从 checkpoint 重新运行复现”；源 Python 环境当前不可执行，checkpoint forward 仍待 Phase 1 验证。

## 完整来源链

```text
真实 CSV
→ data_provider/data_loader.py 的时间顺序划分与标准化
→ DGraFormer checkpoint
→ demo_inference.py / demo_adjacency.py / extract_attention.py
→ demo_results/<dataset>_96/*.npy
→ export_demo_json.py
→ public/data/samples/*.json
→ src/data/loaders.ts
→ 网页
```

## 网页样本到真实测试索引

| 数据集 | 网页 sample 0–4 对应测试索引 |
|---|---|
| ETTh1 | 0, 537, 1074, 1611, 2148 |
| ETTh2 | 0, 537, 1074, 1611, 2148 |
| ETTm1 | 0, 2278, 4556, 6834, 9112 |
| ETTm2 | 0, 2278, 4556, 6834, 9112 |
| Weather | 0, 2073, 4146, 6219, 8292 |

这些映射由导出器的 `stride = total_test_samples // 5` 和 `real_id = web_id * stride` 确定。具体输入及预测时间范围可由 CSV 时间列、测试 border 和上述索引确定。

## 数据与 checkpoint

五份真实 CSV、五个单 seed checkpoint 均已找到并记录 SHA-256，详见 `artifacts/preflight/input_manifest.json`。ETT 数据采用固定 12/4/4 月划分；Weather 使用按时间顺序的 70%/10%/20% 划分。测试加载器关闭 shuffle，因此保存数组顺序与测试索引一致。

## 图数据边界

`adjs.npy` 来自 `exp.model.model.gc(..., current_epoch=71)`，即 `Graph_constructor.forward` 返回的最终矩阵：ReLU/tanh 后、去对角、模型全局 Top-K、加自环并行归一化后的矩阵。

当前网页导出器随后又执行一次固定 40% Top-K，并把同一个模型最终矩阵同时写入 `static_graph` 与 `dynamic_graph`。因此：

- 网页 `dynamic_graph` 可回溯到模型最终归一化矩阵；
- 网页 `static_graph` 不是模型原始静态先验；
- 网页 `sparse_graph` 是导出器二次加工，不是模型真实 Top-K 阶段；
- `kept_edges` 的 `w > 0.15` 标记也不是模型 mask。

## Phase gate

Phase 0 审计已经完成，但 `can_enter_phase_1 = false`。必须先恢复可执行的 PyTorch 环境并锁定配置/代码版本，才能执行指示书要求的 checkpoint 基线复现。
