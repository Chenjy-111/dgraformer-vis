# ETTh1 预计算候选干预与证据目录

## 范围

- 数据集：ETTh1
- checkpoint SHA-256：`f6abbd4e9b32ae80851f42d5476069c41c66b900b181f9f24c56d445a1cead9f`
- 数据 SHA-256：`f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066`
- canonical graph schedule：`current_epoch_equivalent=5`，`0.1 static + 0.9 learned`
- 测试样本索引：`0, 537, 1074, 1611, 2148`
- 所有边均标记为 `Candidate Pattern`；选择不代表重要性结论。

## 预声明候选边

| 候选边 | Phase 3 类别 | 真实保留窗口 |
|---|---|---|
| HUFL→MUFL | high-weight/low-frequency；window-specific | 0 |
| HUFL→MULL | high-weight/low-frequency；window-specific | 1 |
| HUFL→LUFL | high-frequency/low-weight | 0, 1, 6 |
| LULL→LUFL | high-frequency/low-weight | 1, 2, 4 |

选择规则在 `configs/precomputed_intervention_catalog.json` 中预先固定。候选按 Phase 3 的结构字段排序并去重，未查看干预结果后重新挑选。

## Phase 4 预计算干预

- run_id：`db40ee6d94c577e978a06b6aaba50cee209ea13f98b4a6d03a7ed5f4d39e107c`
- 记录数：80
- 真实 forward：85（5 次 baseline + 80 次 intervention）
- 协议：`structural_edge_removal`、`normalized_channel_mask`
- identity override：逐样本严格复现 baseline
- catalog：`artifacts/runs/<run_id>/catalog/ETTh1.json`
- 原始预测：`artifacts/runs/<run_id>/predictions/ETTh1.npz`

Phase 4 记录只表示真实模型干预已计算；不得自动称为已通过统计验证。

## Phase 5 预计算证据

- run_id：`3e6ed8ca27a3f6fd83dec960f0a0091c9497d4ea8cdc1cbeafa1ae88d7161cc3`
- 正式案例：40
- 匹配对照记录：4,000（每案例 100 次）
- bootstrap：每案例 10,000 次
- 多重比较：全部 40 个案例作为同一比较族执行 Benjamini–Hochberg 校正
- identity override：25 个样本—窗口组的最大绝对差均为 `0.0`

真实结果摘要：

- MAE 增加：17 个案例
- MAE 降低：11 个案例
- MAE 严格不变：12 个案例
- prediction delta abs 范围：`0.0` 至 `0.003582454752177`
- empirical p 范围：`0.168316831683168` 至 `1.0`
- BH adjusted p：40 个案例均为 `1.0`
- 12 个案例的对照影响标准差为 0，因此 standardized effect size 数学上未定义；对应值为 `null`，并逐项记录 `status: undefined` 和原因。

不得将上述结果改写为候选边已被证明重要。零影响、误差降低和统计不支持结果必须在前端保留。

## Cross-Run

仍为 `missing / not evaluated / deferred`。只有一个真实 ETTh1 checkpoint，所有跨训练指标继续为 `null`。

## 验证

- 相同命令复跑的 intervention manifest 逐字节一致。
- 相同命令复跑的 evidence manifest 逐字节一致。
- Python tests：17/17 通过。
- TypeScript：通过。
- Vite production build：通过，仅有既有 chunk-size warning。

本轮生成的 `854a9cf...` 是在补充 undefined metric 状态说明之前的中间运行，不是当前正式 evidence catalog；`197d2df...` 仅是早期 plan-only 目录。正式网页只应引用上面列出的两个 canonical run_id。
