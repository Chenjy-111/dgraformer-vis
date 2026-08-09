# Content and Data Authenticity Audit

## 范围

审计覆盖网站 `src/`、`scripts/`、`public/`，以及 `DGraFormer-main` 中的模型、数据加载器、checkpoint、CSV、NPY 与导出脚本。真实模型产物已找到，但仍需区分模型输出和导出器二次加工。

## A. 随机性

- `src/components/GraphNetwork.tsx` 中的 `mulberry32(seed)`：用于固定种子的图节点布局，不生成科研数值。可保留，但不得被误称为模型随机种子。
- 未发现 `Math.random()`、`torch.rand()`、`torch.randn()`、`np.random` 或 `numpy.random` 用于生成网页科学结果。

## B. 模拟、合成与占位内容

- `src/data/paperMetrics.ts`：`SYNTH_FACTORS` 为 PatchTST、TimesNet、DLinear、Crossformer 生成 illustrative 指标。这些不是已核验实验结果，必须在正式科研结果界面禁用或删除。当前标记：`blocked_from_scientific_evidence`。
- `scripts/export_demo_data.py`：模型导入、数据加载和推理为 TODO；脚本不可执行完成导出。当前标记：`placeholder_exporter`。
- `public/data/samples/*.json`：history、ground truth、prediction、动态图和注意力已与真实 NPY 逐值匹配。当前标记：`verified_against_saved_run_arrays`；尚未完成 checkpoint 重新 forward。
- `public/data/metrics.json` 与 `src/data/paperMetrics.ts`：论文转录指标未附表格页码、版本哈希或原始操作数追踪。只能视为文献转录，不能混同本地真实运行结果。

## C. 启发式与推测性内容

- `src/engine/errorDiagnosis.ts::diagnose`：依据固定阈值将误差、远期步、图变化、稀疏度和注意力扩散组合成诊断线索；属于指示书禁止的启发式原因猜测。当前标记：`must_disable_before_release`。
- `src/engine/graphAnalysis.ts::recomputeTopK`：根据 UI 滑杆对已导出图执行二次 Top-K，不一定等于模型实际 Top-K。不得作为真实模型图证据。当前标记：`descriptive_ui_only`。
- `src/engine/graphAnalysis.ts::computePriorC`：在浏览器从 history 重算余弦矩阵，不是已证明的 DGraFormer 原始图阶段。当前标记：`descriptive_ui_only`。
- `src/engine/graphAnalysis.ts::classifyNodeRole`：以固定度数阈值生成 hub/sink/peripheral 标签。只能标为候选描述，不能称为重要性或因果性。当前标记：`must_relabel_or_disable`。
- `src/engine/explanationEngine.ts`：包含“useful”“important”“why it hurts”“largest degradation”等解释性模板，以及将高权重/Top-K 与模型用途直接联系的表述。没有干预与匹配对照支持时不得作为科学结论。当前标记：`must_rewrite_after_real_evidence`。
- `src/components/ErrorDiagnosisView.tsx` 与 `src/components/ExplanationModeGallery.tsx`：向用户展示上述诊断提示。当前标记：`must_disable_before_release`。

## D. 前端派生值

以下值可作为对当前 JSON 的确定性描述，但必须清楚标注“由静态 JSON 在浏览器内计算”，不可写成真实 checkpoint 的新实验结果：MAE/MSE 重算、边排序、窗口出现频率、注意力集中度、前后半段误差均值、图差分。

## E. 处理决定

Phase 0 不新增解释、诊断、模式发现或干预结果。真实保存数组已通过来源对照；启发式诊断、合成 baseline、导出器二次 Top-K 和阶段标签错误仍不得作为科学证据。下一步必须先修复可执行环境、固定配置与代码指纹，再进行 Phase 1 checkpoint 基线复现。
