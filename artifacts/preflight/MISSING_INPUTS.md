# Phase 0 剩余阻塞项

真实 CSV、checkpoint、模型源码和保存的推理数组均已找到；25 个网页样本已与 NPY 原始数组逐值对照。本文件仅保留尚未满足 Phase 1 门禁的项目。

## 缺失项

### 可执行的 Python 3.9 环境
- 当前状态：环境目录存在，但解释器入口失效
- 预期路径：`dgra_env_cuda/Scripts/python.exe`
- 用途：加载 checkpoint，并用相同模型与测试数据重新执行 forward
- 阻塞模块：基线等价验证、真实图阶段重提取、全部干预实验
- 用户需要提供：恢复 Python 3.9.13 基础解释器，或提供可执行且依赖一致的新环境
- 禁止采用的替代方案：把 NPY 对照当作 checkpoint 重新推理、用随机模型替代

### 源码 Git commit
- 当前状态：缺失；提供目录不含 `.git`
- 预期路径：项目 Git 仓库元数据或明确 commit
- 用途：固定模型、数据加载、图构造和导出实现版本
- 阻塞模块：run_id、证据追踪、复现报告
- 用户需要提供：原始 Git 仓库/commit，或确认以当前核心源码文件 SHA-256 作为临时代码指纹
- 禁止采用的替代方案：填写网页仓库 commit 或虚构 commit

### 不可变配置文件
- 当前状态：缺失；参数分散在 `run.py`、多个 demo 脚本和目录名中
- 预期路径：例如 `configs/<dataset>_96.yaml`
- 用途：固定 dataset、checkpoint、seed、窗口、Ke、current_epoch 和全部超参数
- 阻塞模块：确定性复现、run_id
- 用户需要提供：原训练配置；也可在下一阶段从已核验脚本生成配置草案后由用户确认
- 禁止采用的替代方案：静默选择冲突脚本中的默认值

### 未经二次加工的图阶段导出
- 当前状态：缺失
- 预期路径：每个样本/窗口的 raw score、激活后、去对角、模型 Top-K、自环、归一化矩阵
- 用途：区分模型真实矩阵与网页导出器二次 Top-K
- 阻塞模块：Graph provenance、Pattern Discovery、Intervention
- 用户需要提供：无需额外文件；环境修复后可从 `Graph_constructor.forward` 增加审计钩子重新提取
- 禁止采用的替代方案：把网页 `static_graph`、`dynamic_graph`、`sparse_graph` 当作三个真实模型阶段

### 多随机种子 checkpoint
- 当前状态：缺失；每个数据集仅发现一个 checkpoint
- 预期路径：同数据、同划分、同架构和同训练协议的多个真实 seed 运行
- 用途：Cross-Run Validation
- 阻塞模块：Phase 6
- 用户需要提供：多个训练 seed 的 checkpoint、配置、日志与测试指标
- 禁止采用的替代方案：复制单一 checkpoint 或随机扰动结果
