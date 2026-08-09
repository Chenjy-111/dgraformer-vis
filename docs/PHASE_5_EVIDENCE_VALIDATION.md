# Phase 5 Evidence Validation

## 1. 本阶段目标

在真实 checkpoint forward 上测量预先选定候选边的预测与误差影响，并使用同窗口真实保留边进行匹配对照和统计检验。

## 2. 已完成内容

- 对 ETTh2 测试样本 0、窗口 0 的预先选定边 HULL→LULL（1→5）执行结构删除。
- 对窗口内全部 18 条真实保留非自环边逐一执行相同干预。
- 计算权重—影响 Spearman 和 Overlap@5。
- 固定随机种子 `20260807`，从同窗口真实保留边执行 100 次真实 checkpoint 匹配对照。
- 计算经验 p 值、BH 校正、标准化效应量和 10,000 次 bootstrap 置信区间。
- 保存每次对照的抽样边、配置、指标和真实预测数组；负结果未被筛除。

## 3. 修改文件

- `configs/evidence_validation.json`：预先固定样本、候选选择规则、对照次数和随机种子。
- `dgraudit/cli/validate_pattern.py`：真实干预、权重—影响分析、对照实验、统计检验及证据导出。
- `tests/test_evidence_validation.py`：公式、BH、哈希、复现命令和占位内容检查。

## 4. 使用的真实输入

- 数据：`ETTh2.csv`，SHA-256 `a3dc2c597b9218c7ce1cd55eb77b283fd459a1d09d753063f944967dd6b9218b`
- checkpoint SHA-256：`0aaeacc61e1fee9d63f32280c23a4e9ab63133d3c61a3e13a34a7c6fcc5e913e`
- 测试样本索引：`0`
- 输入时间：`2017-06-26 00:00:00` 至 `2017-06-29 23:00:00`
- 预测时间：`2017-06-30 00:00:00` 至 `2017-07-03 23:00:00`
- 图调度：最终状态，`current_epoch` 等价值 `5`
- 对照随机种子：`20260807`

## 5. 执行命令

```bash
python -m dgraudit.cli.validate_pattern --config configs/evidence_validation.json --registry configs/phase1_registry.json --output-root artifacts/runs
```

## 6. 得到的真实数值

- 候选边平均绝对预测变化：`0.0016103379894047976`
- 相对预测变化：`0.0011957044852604335`
- MAE：`0.2701793611049652 → 0.27039116621017456`
- MAE 差值：`+0.00021180510520935059`
- MSE 差值：`+0.00018614530563354492`
- 18 条边权重—影响 Spearman：`rho=-0.013415892672858616`，`p=0.9578637574487228`
- Overlap@5：`0.2`
- 100 次对照平均预测变化：`0.002282499800203368`
- 候选影响对照百分位：`25.0`
- 经验 p 值：`0.7524752475247525`
- BH 校正 p 值：`0.7524752475247525`
- 标准化效应量：`-0.7096858525007002`
- 候选影响减对照均值的 95% bootstrap CI：`[-0.0008535043674564805, -0.0004853464539628475]`

## 7. 代码依据

- 适配器：`dgraudit/adapters.py::DGraFormerAdapter.predict_with_graph_override`
- 模型图位置：`layers/DGraFormer_framework.py`
- Git commit：原始模型目录缺少 Git 元数据，记录为 missing；以文件 SHA-256 追踪。

## 8. 复现轨迹

- run_id：`9b3eeeeb8ef2967cc7fe44a09ac41f214ce9442a890b74d112341cbec0c6f708`
- manifest、environment、command、logs、inputs、graphs、predictions、metrics、controls、evidence 和 report 均位于该运行目录。

## 9. 测试结果

- 相同命令重复运行产生相同 run_id 和逐字节相同 manifest。
- identity override 最大绝对预测差异：`0.0`。
- 单元与证据结构测试全部通过。

## 10. 当前可以得出的结论

在指定 checkpoint、测试样本和窗口中，删除候选边产生了可测量但小于本次匹配对照平均水平的预测变化。本窗口没有观察到图权重与单边删除预测影响的单调关系。

## 11. 当前不能得出的结论

不能声称该边是重要关系、现实因果关系或跨训练稳定解释；也不能把单样本结果推广到整个数据集。

## 12. 缺失输入与阻塞项

- 缺少同一配置下至少 3 个不同随机种子的真实 checkpoint。
- Phase 6 跨训练复核因此仍被阻塞。

## 13. 下一阶段

Phase 6 Cross-Run：获得多随机种子 checkpoint 后进行性能相近筛选、结构重复性和功能重复性验证。
