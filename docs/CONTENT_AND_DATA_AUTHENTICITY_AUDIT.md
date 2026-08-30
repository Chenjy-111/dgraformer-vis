# Content and Data Authenticity Audit

## 范围

审计覆盖网站 `src/`、`scripts/`、`public/`，以及 `DGraFormer-main` 中的模型、数据加载器、checkpoint、CSV、NPY 与导出脚本。真实模型产物已找到，但仍需区分模型输出和导出器二次加工。

## A. 随机性

- `src/components/GraphNetwork.tsx` 中的 `mulberry32(seed)`：用于固定种子的图节点布局，不生成科研数值。可保留，但不得被误称为模型随机种子。
- 未发现 `Math.random()`、`torch.rand()`、`torch.randn()`、`np.random` 或 `numpy.random` 用于生成网页科学结果。

## B. 模拟、合成与占位内容

- `src/data/paperMetrics.ts`：已从投稿版删除；synthetic baseline 不再存在可调用路径。当前标记：`removed_from_submission_build`。
- `scripts/export_demo_data.py`：模型导入、数据加载和推理为 TODO；脚本不可执行完成导出。当前标记：`placeholder_exporter`。
- `public/data/samples/*.json`：history、ground truth、prediction、动态图和注意力已与真实 NPY 逐值匹配。当前标记：`verified_against_saved_run_arrays`；尚未完成 checkpoint 重新 forward。
- `public/data/metrics.json` 与 `src/data/paperMetrics.ts`：论文转录指标未附表格页码、版本哈希或原始操作数追踪。只能视为文献转录，不能混同本地真实运行结果。

## C. 启发式与推测性内容

- `src/engine/errorDiagnosis.ts::diagnose`：历史模块保留在源码中以避免覆盖既有工作，但投稿版无任何组件导入或调用它。预测页不再将误差峰值映射到图窗口或 MSGNet 尺度。当前标记：`unreachable_in_submission_ui`。
- 浏览器二次科学 Top-K：`recomputeTopK` 已删除。3D 滑杆只在模型已保留的 artifact 边集合内控制可见数量和显示阈值，不改写 `kept`，不生成新图，也不影响预测、干预、对照或统计结果。当前标记：`visual_visibility_filter_only`。
- history prior：`computePriorC` 已删除；静态先验只从保存的 artifact 字段读取。当前标记：`removed`。
- 节点角色：`classifyNodeRole` 已删除；投稿版不生成 hub/sink/peripheral 角色。当前标记：`removed`。
- `src/engine/explanationEngine.ts`：已删除；“useful”“important”“why it hurts”等未经干预支持的解释模板不再有可调用路径。当前标记：`removed`。
- `ErrorDiagnosisView.tsx`、`TopKFocusingView.tsx` 与 `ExplanationModeGallery.tsx`：已从投稿版删除。右侧栏已改为只读 artifact 字段，不生成解释或重要性判断。当前标记：`removed_or_replaced`。

## D. 前端派生值

以下值可作为对当前 JSON 的确定性描述，但必须清楚标注“由静态 JSON 在浏览器内计算”，不可写成真实 checkpoint 的新实验结果：MAE/MSE 重算、边排序、窗口出现频率、注意力集中度、前后半段误差均值、图差分。

## E. 处理决定

Phase 0 不新增解释、诊断、模式发现或干预结果。真实保存数组已通过来源对照；启发式诊断、合成 baseline、导出器二次 Top-K 和阶段标签错误仍不得作为科学证据。下一步必须先修复可执行环境、固定配置与代码指纹，再进行 Phase 1 checkpoint 基线复现。
