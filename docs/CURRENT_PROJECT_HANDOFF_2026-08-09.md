# DGraInsight 当前项目交接报告

> 更新时间：2026-08-09（Asia/Shanghai）  
> 用途：将本文件完整提供给下一轮 AI，作为项目目标、当前证据、生产标准、科学红线和后续执行顺序的统一上下文。  
> 原始规范文件：`C:\Users\cj\.codex\attachments\c6897f65-d937-498b-af2b-541847a54532\pasted-text.txt`。该文件仍是最高优先级规范来源；下一轮 AI 必须完整读取，不能只依赖本摘要。

---

# 1. 项目目标与定位

项目名称现统一为 **DGraInsight**。它不是单纯的 DGraFormer 论文展示页面，也不是根据图权重自由生成解释的系统，而是面向动态图多变量时序预测研究者的解释性研究工具。

核心工作流：

```text
真实动态图提取
→ 候选模式发现
→ 真实模型干预
→ 匹配对照与统计验证
→ 跨训练复核（当前延期）
→ 证据与复现报告
```

系统的用户入口是“动态图模式发现”，科学验证方式是“真实 checkpoint 干预、匹配对照和统计检验”，可信保障是“完整复现轨迹”。

系统只能支持如下层级的结论：

> 某个图模式在指定数据、checkpoint、测试样本和图窗口条件下出现；在模型内部干预后产生了可测量的预测变化；该变化可与预先定义的真实边对照进行比较。

系统不得声称发现现实变量之间的因果关系。

---

# 2. 工作区和真实输入位置

## 网站工作区

```text
C:\Users\cj\Desktop\files (1)\dgraformer-vis
```

## 原始 DGraFormer 代码、数据和 checkpoint

```text
C:\Users\cj\Desktop\DGraFormer-main\DGraFormer-main
```

## 原始实施指示书

```text
C:\Users\cj\.codex\attachments\c6897f65-d937-498b-af2b-541847a54532\pasted-text.txt
```

下一轮 AI 必须保留当前工作区中所有未提交修改。特别注意：`src/engine/errorDiagnosis.ts` 含用户既有修改，不得覆盖或回退。禁止使用 `git reset --hard`、`git checkout --` 等破坏性命令。

---

# 3. 当前总体状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| Phase 0 真实性与来源审计 | 完成 | 真实数据、checkpoint、代码、样本索引和哈希已登记 |
| Phase 1 基线预测复现 | 完成 | 25/25 样本独立复跑，最大差异 0.0 |
| Phase 2 真实动态图提取 | 完成 | 全部图构造阶段已提取并验证 |
| Phase 3 Pattern Discovery | 完成 | 候选边、频率、变量角色和局部边集合已生成 |
| Phase 4 Intervention | 完成 | 8 类干预均通过真实 checkpoint forward |
| Phase 5 Evidence Validation | 完成（预声明单案例范围） | 100 次真实边对照、相关性和统计检验已完成 |
| Phase 6 Cross-Run | `missing / not evaluated / deferred` | 每个数据集只有一个真实 checkpoint，不生成替代数据 |
| Phase 7 前端重构 | 主要叙事已接入，仍可继续完善 | 首页、Evidence Validation、Cross-Run 缺失态、证据链已接入；不是实时后端推理平台 |

当前项目主线选择：**不因 Cross-Run 重新训练阻塞主要交付**。Phase 6 作为未来扩展保留，所有相关指标必须为 `null` 并显示缺失原因。

---

# 4. epoch / 图调度问题的最终修正

DGraFormer 的 `current_epoch` 不只是训练记录，还直接参与图混合：

```text
proportion = min(current_epoch / 5, 0.9)
graph = (1 - proportion) × static_prior + proportion × learned_graph
```

因此：

- `current_epoch=1`：0.8 静态 + 0.2 学习；
- `current_epoch>=5`：0.1 静态 + 0.9 学习，调度已饱和；
- epoch 5 与 epoch 71 对图调度等价；
- `current_epoch=5` 不表示模型只训练了 5 轮；
- checkpoint 的真实训练轮数不能由该参数推断。

此前旧产物存在“预测使用 epoch 等价值 1、图使用 71”的混合。现已全部统一为：

```text
真实训练后 checkpoint
+ final graph schedule
+ current_epoch_equivalent = 5
+ static_weight = 0.1
+ learned_weight = 0.9
```

没有为修正该问题重新训练模型。

旧混合产物已标记为 `superseded`，不得用于网站结果或科学结论。

---

# 5. 真实输入、配置与哈希

## 核心配置

- 随机种子：`202501`
- 输入长度：`96`
- label 长度：`48`
- 预测长度：`96`
- 图窗口大小：`24`
- 图窗口数量：`7`
- `d_graph=30`
- `d_gcn=1`
- `w_ratio=0.5`
- message passing layers：`2`
- patch length / stride：`8 / 8`
- `d_model=16`
- heads：`4`
- encoder layers：`1`
- `d_ff=128`
- 全局 Top-K 槽数：`floor(N × N × 0.5)`，代码在去对角后执行全局 Top-K，槽数计算仍包含完整 `N×N` 空间。

## 源代码哈希

| 文件 | SHA-256 |
|---|---|
| `models/DGraFormer.py` | `dbfd103577e6f54109642f0f3ce884ede54aab16c6bcef634f2b763f3257b35d` |
| `layers/DGraFormer_framework.py` | `68ce6d05c68aa2fd901298297220b6d97b41e66b6812c124317ef77c763f36c4` |
| `data_provider/data_loader.py` | `b763e649dbdf4b1b2e3da625b0186bc9ae66744755faf07719c18103a9e25c02` |
| `run.py` | `12bc3c127a54fc0d4bb774a3ba15b660f6dbfd519724d9b1a5a6fc81ccfc832d` |

原始模型目录缺少 Git 元数据和不可变 commit。必须明确记录为 `missing_repository_metadata`，以文件哈希追踪；不得虚构 commit。

## 数据与 checkpoint

| 数据集 | 数据 SHA-256 | checkpoint SHA-256 | 网站测试索引 |
|---|---|---|---|
| ETTh1 | `f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066` | `f6abbd4e9b32ae80851f42d5476069c41c66b900b181f9f24c56d445a1cead9f` | 0, 537, 1074, 1611, 2148 |
| ETTh2 | `a3dc2c597b9218c7ce1cd55eb77b283fd459a1d09d753063f944967dd6b9218b` | `0aaeacc61e1fee9d63f32280c23a4e9ab63133d3c61a3e13a34a7c6fcc5e913e` | 0, 537, 1074, 1611, 2148 |
| ETTm1 | `6ce1759b1a18e3328421d5d75fadcb316c449fcd7cec32820c8dafda71986c9e` | `b065f4048f05fb2544070ef5652c382f501fb2f070bb0e352f30e46dddaa55fa` | 0, 2278, 4556, 6834, 9112 |
| ETTm2 | `db973ca252c6410a30d0469b13d696cf919648d0f3fd588c60f03fdbdbadd1fd` | `c02b9e45475d23d82f5bf78e2436f636e992e775e1df6ff5cdb3f08863bf873f` | 0, 2278, 4556, 6834, 9112 |
| Weather | `34ee981d07313e51da2a50bb600072c8ae4a69cb4b0651f4cb93a069d7a2ba63` | `3fda08db93fffeb41808056fb6fe1ae93994ce29c1791f96407e0478039d5503` | 0, 2073, 4146, 6219, 8292 |

---

# 6. 规范运行链与证据位置

| 产物 | canonical run_id |
|---|---|
| 网站 canonical export | `d40384ae455ec45e642761902f354b38649411e45cdbd5f3f98d1b3811fa5ca9` |
| Phase 1 baseline | `f654f2ab710e4e51f3e7086736b32b9f064ff84f1e4ae8a0053bfdc448b36de9` |
| Phase 2 graph extraction | `bc60c5a9f09c46d5e176a2e014bb7b516c7c562270f86c31bb382ee48342175b` |
| Phase 3 pattern discovery | `467d53169372e3120e7964f81152bee863fc5ef121b01e5413ed813c14c10a5c` |
| Phase 4 intervention | `0ce6faf89f74cf6e4bc67a109bd47ef190f2cd8299ec03a3eb431a88728664d0` |
| Phase 5 evidence validation | `9b3eeeeb8ef2967cc7fe44a09ac41f214ce9442a890b74d112341cbec0c6f708` |

每个正式运行目录位于：

```text
artifacts/runs/<run_id>/
```

应包含适用的：

```text
manifest.json
command.txt
environment.json
stdout.log
stderr.log
inputs/
graphs/
predictions/
metrics/
controls/
evidence/
report/
```

当前总审计清单：`artifacts/preflight/input_manifest.json`。

---

# 7. 各阶段真实结果

## Phase 0

- 真实 checkpoint、真实数据文件和模型代码均可加载。
- 网站 25 个样本已建立真实测试索引映射。
- 旧网页产物来源和 epoch 混合问题已审计。
- 缺失 Git commit 和独立不可变训练配置已明确记录，未使用替代值。

## Phase 1

- 25/25 个网页样本使用真实 checkpoint 独立重放。
- 与 canonical final-schedule export 的最大绝对预测差异：`0.0`。
- 平均绝对差异：`0.0`。

## Phase 2

提取并保存每个窗口的：

- 静态先验；
- 混合 raw score；
- 激活后分数；
- 去对角分数；
- 全局 Top-K mask；
- Top-K 图；
- 加自环图；
- 实际用于消息传递的行归一化图。

与原始 `adjs.npy` 最大差异：ETTh1 `5.960464477539063e-08`，其余数据集 `0.0`。

## Phase 3

已发现并保存：

- persistent edge；
- window-specific edge；
- high-weight low-frequency edge；
- high-frequency low-weight edge；
- sender / receiver roles；
- repeated local edge sets。

所有结果只能标记为 `Candidate Pattern` 或 `structural_candidate`，不得称为 important、true 或 causal。

## Phase 4

真实执行 8 类干预：

1. structural edge removal；
2. normalized channel mask；
3. variable outgoing removal；
4. variable incoming removal；
5. variable associated-edge removal；
6. input variable mask；
7. candidate edge-set removal；
8. keep candidate edge set only。

全部结果来自真实 checkpoint forward。identity graph override 与未干预 forward 完全一致，最大绝对差异 `0.0`，证明干预接入点在无修改时不会改变原模型。

## Phase 5

预声明检验对象：

- 数据集：ETTh2；
- 测试样本：0；
- 窗口：0；
- 候选边：HULL→LULL（1→5）；
- 干预：structural edge removal；
- 对照：同窗口真实保留非自环边；
- 对照次数：100；
- 对照随机种子：20260807；
- bootstrap 次数：10,000。

真实数值：

| 指标 | 结果 |
|---|---:|
| baseline MAE | `0.2701793611049652` |
| intervention MAE | `0.27039116621017456` |
| prediction delta abs | `0.0016103379894047976` |
| prediction delta rel | `0.0011957044852604335` |
| error delta MAE | `+0.00021180510520935059` |
| error delta MSE | `+0.00018614530563354492` |
| retained edge count | `18` |
| weight-impact Spearman rho | `-0.013415892672858616` |
| Spearman p | `0.9578637574487228` |
| Overlap@5 | `0.2` |
| matched-control mean impact | `0.002282499800203368` |
| candidate control percentile | `25.0` |
| empirical p | `0.7524752475247525` |
| BH adjusted p | `0.7524752475247525` |
| standardized effect size | `-0.7096858525007002` |
| 95% bootstrap CI of candidate-minus-control-mean | `[-0.0008535043674564805, -0.0004853464539628475]` |

这是必须保留的负结果，不得隐藏或改写成支持候选重要性的结果。

## Phase 6

状态文件：`artifacts/cross_run/status.json`。

当前状态：`missing / not evaluated / deferred`。

原因：每个数据集仅有一个真实 checkpoint。没有生成以下替代值：

- checkpoint performance screening；
- edge Jaccard；
- edge recurrence frequency；
- weight correlation；
- intervention impact consistency；
- error-direction consistency。

这些字段必须保持 `null`，不能填 0，不能用窗口差异或随机模型冒充不同训练运行。

## Phase 7

已完成主要前端叙事改造：

- 首页品牌改为 DGraInsight；
- Problem & User Value 改为动态图解释验证问题；
- 保留真实样本、预测、图、注意力工作区；
- 新增 Evidence Validation 区块；
- 展示候选影响与匹配对照均值；
- 展示 Spearman、Overlap@5、经验 p、BH 校正、效应量和置信区间；
- 提供网页 evidence JSON 下载；
- Cross-Run 显示 `Not evaluated` 和 `null`；
- 新增 Select→Discover→Intervene→Validate→Trace 工作流；
- 更新科学边界。

当前网站仍是静态审计产物浏览器，不是 FastAPI 实时推理服务。不得声称用户在浏览器点击后会即时重新运行 checkpoint，除非未来确实实现并验证后端。

---

# 8. 当前测试和构建结果

- Python 自动测试：`12/12` 通过。
- TypeScript：`tsc -b` 通过。
- Vite production build：通过。
- 构建产物：`dist/`。
- Vite 仅有 chunk 大小警告，不是构建失败。
- 相同 Phase 5 命令重复执行：run_id 相同，manifest SHA-256 逐字节一致。
- identity override 最大绝对预测差异：`0.0`。
- 25 个网站样本 final-schedule replay：最大预测差异 `0.0`。

已覆盖的测试包括：

- 图去对角、Top-K、自环和归一化基本不变量；
- structural removal 重新归一化；
- normalized channel mask 不重新归一化；
- incoming removal；
- candidate 标签；
- Phase 5 指标公式；
- Benjamini–Hochberg；
- evidence 数据、checkpoint、配置哈希；
- reproduction command；
- 禁止 placeholder/mock/dummy/fake 被标为完成；
- computed metrics 不使用 null。

原始指示书列出的完整测试矩阵仍是长期验收标准。下一轮如继续开发，应补足尚未显式实现的命名测试，而不能仅以当前 12 个测试声称覆盖全部最终验收项。

---

# 9. 当前可以得出的结论

允许结论：

> 在指定 DGraFormer checkpoint、ETTh2 测试样本 0 和图窗口 0 中，删除候选边 HULL→LULL 后，平均绝对预测变化为 0.001610，MAE 增加 0.000212。该影响位于 100 次同窗口真实边匹配对照的第 25 百分位，经验 p 为 0.752475。窗口内 18 条保留边的图权重与删除影响之间的 Spearman rho 为 -0.013416，p 为 0.957864。

基于该实验，可以描述：

- 候选边删除产生了可测量但较小的模型预测变化；
- 候选影响小于本次匹配对照平均水平；
- 本窗口没有观察到图权重和单边删除预测影响之间的单调关系；
- 高图权重不能在该案例中直接当作高功能影响证据；
- 结果是指定模型内部行为，不是现实因果结论。

---

# 10. 当前不能得出的结论

禁止声称：

- HULL 导致 LULL 发生现实变化；
- 该边是真实关系、因果关系或主要原因；
- 该候选边已经证明重要；
- 高权重边一般都重要或一般都不重要；
- 单个样本结论能代表整个 ETTh2 数据集；
- 结果能推广到其他数据集、模型或 checkpoint；
- 该图解释具有跨训练稳定性；
- 系统提高了用户效率（除非未来有用户实验）；
- 浏览器正在实时运行模型（当前没有）；
- Cross-Run 已经完成。

---

# 11. 最高优先级生产标准与科学红线

以下规则优先于界面美观、动画、页面完整度、演示效果和开发速度。

## 11.1 所有科研数值必须来自真实运行

以下内容必须来自真实 checkpoint 和真实测试数据：

- 输入序列；
- 真实标签；
- 预测；
- 误差；
- 图矩阵及全部构造阶段；
- Top-K mask、边、权重和排名；
- 注意力；
- 干预预测；
- 对照预测；
- 统计结果；
- 置信区间；
- 跨训练结果（未来若执行）。

严禁使用：

```text
Math.random()
torch.rand / torch.randn
numpy.random 生成假输入、预测、边权或标签
手写邻接矩阵
手写预测结果
人工指定误差变化
占位数值伪装成完成结果
预设成功案例
前端临时生成科研结果
随机模型替代真实 checkpoint
```

随机性只允许用于统计抽样，并必须：固定种子、从真实候选集合抽取、保存每次抽样对象、保存每次真实推理结果。随机性不得生成预测、边权或标签。

## 11.2 缺少输入必须停止对应模块

缺少 checkpoint、数据、配置、样本索引、变量名、代码位置或多随机种子 checkpoint 时：

1. 停止被阻塞实验；
2. 返回非零或明确 `missing` 状态；
3. 缺失数值使用 `null`，不能使用 0；
4. 说明缺失原因和所需输入；
5. 前端显示不可用原因；
6. 不得生成替代数据。

## 11.3 不得根据图形或阈值猜测含义

必须删除或禁用：

- 根据误差大小猜测原因；
- 根据窗口位置猜测长期不确定性；
- 根据图变化猜测现实状态变化；
- 根据边权猜测变量重要性；
- 根据注意力分散猜测误差来源；
- 固定阈值生成风险等级；
- 固定模板生成建议；
- 与模型真实 Top-K 无关的二次稀疏化；
- 仅为视觉效果生成的科研数据。

## 11.4 候选、干预证据与因果结论必须分层

- Pattern Discovery 只能输出 `Candidate Pattern`。
- 真实干预后只能输出 `interventional_model_evidence`。
- 统计不支持时必须展示负结果。
- 即使统计支持，也只能描述指定模型内部行为。
- 禁止使用“证明了、一定、真实关系、因果关系、主要原因、建议关注、风险、显然、很可能、大概、异常原因”等表述。
- “显著”只有同时报告检验方法、校正、效应量和置信区间时才允许使用。

## 11.5 图语义必须严格区分

- `static_graph`：静态先验；
- `dynamic_graph`：激活并去对角、Top-K 之前的窗口动态图分数；
- `sparse_graph`：加自环并归一化、实际用于消息传递的最终图；
- Top-K mask、Top-K graph、自环图和 normalized graph 不能混称；
- 前端不得额外应用与模型无关的 Top-K 并冒充模型结果。

## 11.6 干预必须位于真实消息传递位置

- structural edge removal：删除结构边后重新行归一化；
- normalized channel mask：直接屏蔽最终归一化通道，不重新归一化；
- variable / edge-set 协议按明确定义执行；
- 每次结果必须来自真实 checkpoint forward；
- identity override 必须完全复现原 forward；
- 前端不得根据图形差异自行合成干预预测。

## 11.7 匹配对照和统计要求

- 对照必须来自真实边集合；
- 同窗口、同边数、排除自环；
- 保存抽样边、随机种子、干预配置、预测和指标；
- 经验 p 使用加一修正；
- 多重比较使用 Benjamini–Hochberg 或明确记录其他预声明方法；
- 报告置信区间和效应量；
- 不得只展示“成功”或“显著”案例；
- 权重—影响关系必须保存原始权重和原始干预影响数组。

## 11.8 Cross-Run 要求

正式 Cross-Run 至少需要 3 个、推荐 5 个真实不同随机种子 checkpoint。必须固定数据、划分、结构、超参数、训练轮数或早停规则和评价方式，只改变随机种子。性能相近阈值必须预先规定，不能看结果后修改。

不得以不同窗口、Dropout 采样、扰动同一个 checkpoint 或随机模型冒充多个独立训练运行。

## 11.9 Evidence 记录必须完整

每条正式结论应独立保存 JSON，并至少包含：

- conclusion_id、status、claim_level；
- 确定性模板 statement；
- 数据路径和 SHA-256；
- split、原始样本索引和时间范围；
- checkpoint 路径和 SHA-256；
- seed、配置路径和 SHA-256；
- 图窗口、source、target；
- raw score、Top-K score、normalized weight、rank、margin；
- 干预类型、是否重新归一化、实现文件和函数；
- baseline/intervention MAE/MSE；
- prediction delta abs/rel；
- error delta；
- control percentile、empirical p、adjusted p、CI、effect size；
- 原始操作数文件；
- 公式 ID；
- 模型和图代码位置；
- run_id、command、environment、manifest、stdout/stderr；
- limitations。

未计算值必须为 `null`，同时记录 `status: missing` 和原因；不得以 0 表示未计算。

## 11.10 复现链必须贯通

```text
网页结论
→ evidence JSON
→ 指标原始操作数
→ baseline / intervention / control predictions
→ 图矩阵
→ 测试样本
→ checkpoint
→ 模型配置
→ 代码版本或哈希
→ 命令
→ 环境
→ 日志
```

## 11.11 run_id 必须确定性

run_id 应由数据与划分、配置、checkpoint、随机种子、代码版本/哈希和实验配置共同决定。相同输入与配置必须生成相同 run_id。

## 11.12 前端真实性

- 网站只展示真实 artifact 中存在的值；
- artifact 不可用时显示错误或 missing，不生成 fallback 科研数据；
- 不得把描述性网页说成实时推理服务；
- 所有数值应能下载或追踪到 evidence；
- Cross-Run 当前必须显示 Not evaluated；
- 响应式、键盘可访问性和清晰的状态标签仍是产品要求，但不能以牺牲科学真实性实现。

---

# 12. 原计划书完整产品要求（后续仍保留）

最终系统应覆盖以下页面/能力，即使当前版本尚未全部独立路由化：

1. Problem & Value；
2. Pattern Discovery；
3. Intervention Lab；
4. Evidence Validation；
5. Cross-Run Validation；
6. Reproduction Trace；
7. Live Demo Workflow。

理想 Demo 流程：

```text
选择真实样本
→ 发现候选模式
→ 选择边、变量或子图及窗口
→ 选择干预协议
→ 后端真实重新推理
→ 查看预测和误差变化
→ 查看匹配对照
→ 查看跨训练复核或 missing 状态
→ 打开证据轨迹
→ 复制命令或导出报告
```

当前尚未实现 FastAPI 实时后端和现场动态运行；现阶段网站展示的是已审计、预计算、真实运行的 artifacts。下一轮 AI 必须诚实保留这一边界。

---

# 13. 当前网站文件和关键实现

## 科学后端/CLI

- `dgraudit/adapters.py`
- `dgraudit/cli/rebuild_canonical.py`
- `dgraudit/cli/validate_baseline.py`
- `dgraudit/cli/extract_graphs.py`
- `dgraudit/cli/discover_patterns.py`
- `dgraudit/cli/intervene.py`
- `dgraudit/cli/validate_pattern.py`

## 配置

- `configs/phase1_registry.json`
- `configs/pattern_discovery.json`
- `configs/intervention.json`
- `configs/evidence_validation.json`

## 前端

- `src/App.tsx`
- `src/components/Hero.tsx`
- `src/components/ResearchMotivation.tsx`
- `src/components/EvidenceValidation.tsx`
- `src/components/Limitations.tsx`
- `src/components/DynamicGraphView.tsx`
- `src/engine/graphAnalysis.ts`
- `src/types/demo.ts`
- `public/data/samples/*.json`
- `public/data/evidence/phase5_etth2_s0_w0_edge_1_5.json`

## 文档

- `docs/CURRENT_WEB_DATA_PROVENANCE.md`
- `docs/CONTENT_AND_DATA_AUTHENTICITY_AUDIT.md`
- `docs/PAPER_CODE_GRAPH_DIFFERENCES.md`
- `docs/CANONICAL_SCHEDULE_CORRECTION.md`
- `docs/PHASE_1_BASELINE_REPRODUCTION.md`
- `docs/PHASE_2_GRAPH_EXTRACTION.md`
- `docs/PHASE_3_PATTERN_DISCOVERY.md`
- `docs/PHASE_4_INTERVENTION.md`
- `docs/PHASE_5_EVIDENCE_VALIDATION.md`
- `docs/PHASE_6_CROSS_RUN_STATUS.md`

---

# 14. 已知风险与技术债

1. 原始模型目录没有 Git commit；只能使用文件哈希。
2. 原始训练配置从 `run.py` 和 checkpoint 目录名重构，没有不可变 standalone config。
3. Cross-Run 未执行，不能声称跨训练稳定性。
4. Phase 5 当前是预声明的单 checkpoint、单样本、单窗口候选案例，不能推广到全数据集。
5. 前端仍保留部分旧论文展示组件和文案，可能存在编码损坏字符；后续可继续清理，但不得改变科学数值。
6. 当前工作区存在大量未提交修改，下一轮必须先检查 `git status`，不得覆盖用户修改。
7. `dist` bundle 较大，Vite 有 chunk warning；属于性能优化项，不影响当前正确性。
8. 网站未部署本次新版本；除非用户明确授权，不得擅自发布或推送。

---

# 15. 下一轮 AI 建议执行顺序

如果用户希望“继续完善主要内容”，下一轮应按以下顺序：

1. 完整读取本报告和原始指示书。
2. 运行 `git status --short`，识别并保留现有修改。
3. 读取 `artifacts/preflight/input_manifest.json` 和最新 Phase 5 manifest。
4. 不重新开启 epoch=1/71 争论；canonical 状态已经确定为 final schedule / epoch-equivalent 5。
5. 不执行多随机种子训练，除非用户未来明确改变决定。
6. 将 Cross-Run 保持 `missing/null`。
7. 优先完善前端主流程：Pattern Discovery、Intervention、Evidence、Trace 之间的导航与数据关联。
8. 如要新增实验，必须先写配置和选择规则，再运行真实 checkpoint，最后接入前端。
9. 每次新增结论都生成 evidence JSON、raw operands、命令、环境和日志。
10. 运行 Python 测试、TypeScript 编译和 production build。
11. 不做浏览器视觉 QA，除非用户明确要求；不部署，除非用户明确授权。

---

# 16. 给下一轮 AI 的最短启动提示

可将下面这段与本文件一起交给下一轮 AI：

```text
请完整读取 docs/CURRENT_PROJECT_HANDOFF_2026-08-09.md 和原始指示书
C:\Users\cj\.codex\attachments\c6897f65-d937-498b-af2b-541847a54532\pasted-text.txt。

这是 DGraInsight：以动态图候选模式发现为入口，以真实 checkpoint 干预、匹配对照和统计检验为验证，以完整复现轨迹为可信保障。Phase 0–5 已完成；Phase 6 因只有一个 checkpoint 被正式延期并必须保持 missing/null；Phase 7 主叙事已接入但可继续完善。

所有科研数值必须来自真实 checkpoint 和真实测试数据。禁止伪造、占位、前端生成、启发式原因、因果措辞和隐藏负结果。canonical 推理统一使用 final graph schedule：current_epoch 等价值 5，即 0.1 static + 0.9 learned。旧 epoch=1/71 混合产物已废弃。

先检查 git status 并保护所有现有修改，尤其不要覆盖 src/engine/errorDiagnosis.ts。然后根据用户的新请求继续。
```

---

# 17. 当前最终结论摘要

本项目已经证明：

- 网站样本可以从真实 checkpoint 和真实测试数据重新生成；
- 动态图构造各阶段可以准确提取；
- 干预确实发生在模型图消息传递位置；
- 无干预完全复现原模型；
- 可以从真实图中发现候选模式并进行真实干预与匹配对照；
- 当前 ETTh2 案例显示，高图权候选边没有表现出高于普通匹配边的预测影响；
- 图权重不能直接当作功能重要性的证据；
- 负结果、缺失结果和复现边界均已保留。

本项目尚未证明：

- 模式具有现实因果意义；
- 当前结果适用于全数据集或其他模型；
- 解释能够跨独立训练稳定复现；
- 系统已经具备在线实时模型推理服务。

这是当前最准确、可复现且符合原始生产红线的项目状态。
