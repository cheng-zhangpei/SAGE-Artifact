# SAGE 工作流实验：碰撞所迫良性拦截的归因方案

## 实验边界

本轮不把“自动模型精化”扩展为论文贡献。核心对象是模型相对的良性事件，以及 guard 对它们的拒绝来源。

给定固定模型 `M`、策略 `B`、有限事件域 `E`、危险事件 `D` 和良性事件 `G=E\D`，对任意被 guard 拒绝的事件 `e` 归类：

1. `e in D`：模型要求拒绝。没有独立 concrete oracle 时，只称 `model-required denial`，不评价现实误拦。
2. `e in G` 且 `O(e) in O(D)`：`collision-forced benign denial`。任何基于同一 observation 的安全无记忆 controller 都必须拒绝它。
3. `e in G` 且 `O(e) not in O(D)`，但当前 guard 拒绝：`guard-induced avoidable denial`。
4. 域探索不完整且尚未找到危险 observation mate：`unresolved under incomplete domain`。

本文主要解释第 2 类，并用第 3 类连接验证和合成。第 1 类中现实本应允许但模型判危险的问题属于模型确认/精化边界，不在本轮解决。

## 为什么这一归因有贡献

单一 benign blocking rate 将性质不同的问题混在一起：

- collision-forced denial 不能通过重写同一 observation 上的 guard 消除；
- guard-induced denial 可以通过验证、反例和重新合成消除；
- model-required denial 是否为现实误拦，需要模型外证据。

因此 SAGE 不只是报告“拦了多少良性任务”，还给出一个可检查的原因证书：良性事件与哪个危险事件共享 observation、相同 resolved action 是什么、缺失的 event taint 区别是什么。

## 推荐抽样设计

### 第一层：全量 census，保留规模

对当前公开快照全部 10,892 个可解析工作流运行确定性结构分析。报告完整漏斗：

| 集合 | 当前数量 | 用途 |
|---|---:|---|
| 所有可解析模板 | 10,892 | 外部语料范围 |
| 含已识别 LLM 节点 | 5,707 | agentic workflow 范围 |
| 含外部动作候选 | 3,605 | guard 可能适用范围 |
| 含 binary sink | 226 | late-resource 高相关层 |
| 命中当前窄规则 | 38 | 候选全集 |

这一步称为 corpus-wide structural census，不能称为对 10,892 个工作流完成了 SAGE 语义验证。

### 第二层：审查全部 38 个候选，不抽样

38 个数量足够小，应当全部完成最终分类，避免只挑正例：

- `confirmed collision under reviewed contract/policy scenario`；
- `no collision: provenance already reaches ctx`；
- `invalid structural candidate`；
- `policy not applicable`；
- `contract unresolved`。

当前结果：38 个候选全部审查；14 个确认碰撞情景、17 个无碰撞、6 个结构无效、1 个契约未决。31 个可确认项全部进入 SAGE 局部模型。14 个 `O_ctx` 正例在 `O_event` 下均降为 0；模板 15449/15451 为同结构近重复，14 个模板对应 13 种结构。

最终可以报告 `x/38`，但含义必须是“在预定义 late-resource detector 命中的候选全集中，有多少经审查后形成碰撞”，不是所有 n8n 工作流的概率。

同时按结构指纹去重报告。15449 和 15451 指纹相同，应分别给模板数与不同结构数。

### 第三层：从 detector negatives 中做分层随机审计

候选全集审查只能说明 precision 和候选内现象，不能说明规则漏掉多少。因此固定随机种子并从以下互斥层抽样：

1. `binary-negative`：226 个 binary-sink 工作流中未命中窄规则的 188 个，随机抽 50 个。
2. `nonbinary-external`：有外部动作但没有 binary sink 的工作流，随机抽 50 个，用于寻找数据库、API、消息或权限状态造成的非附件碰撞。
3. 可选 `complex-negative`：包含 Code/custom HTTP/跨节点引用且前两层未选中的工作流，额外抽 30 个，作为解析器压力测试。

抽样名单必须在语义判断前固化，保存 seed、ID、结构哈希与纳入/排除原因。LLM 可以协助提取依赖，但所有 LLM-negative 不能直接当作“无碰撞”；人工核验全部提议正例，并随机复核一部分提议负例。

如果时间紧，先完成 38 个全集＋两个 50-workflow 层。第三层主要检查 detector 的外部有效性，不参与主碰撞比例。

## 每个候选的统一建模协议

### 固定数据

- 原始公开 JSON 和 SHA256；
- 节点版本、main/data connections、named expressions；
- agent 实际读取的字段；
- sink 实际读取的字段和 resolved parameters；
- late resource 的 provenance；
- 策略族与适用依据。

### 成对事件

为适用的策略场景构造一对执行：

- agent context、resolved sink action、recipient 和非目标输入相同；
- late resource 分别为允许标签与禁止标签；
- full/event model 能区分二者；
- 不通过清空本应存在的 ctx label 制造碰撞。

只有原始数据依赖支持“资源没有进入 ctx”时，才允许进入碰撞检查。如果 AI 已读取附件文本、图片、摘要或其他同源派生物，union-flow 下 provenance 已经进入 ctx，应当作为负例。

### 策略控制

采用预先定义的策略族：private source 到 external/public sink、recipient-scoped data 到其他 recipient、internal template 到 prospect/customer。若原工作流没有足够身份边界支持该策略，标记 `policy not applicable`。

策略和标签由研究场景补充时，结论表述为 collision susceptibility under an explicit policy scenario，不能声称原作者部署已经发生误拦。

## RQ 设计

### RQ1：公开工作流中是否存在观测碰撞结构？

在 38 个候选全集中报告最终五类状态、模板数、去重结构数及具体 witness。存在性结论由最保守子集支撑，不依赖发生率。

### RQ2：良性拒绝中有多少是碰撞所迫？

对每个已建模工作流和每种 guard，批量统计：

- model-dangerous denials；
- collision-forced benign denials；
- guard-induced avoidable denials；
- unresolved denials。

主指标不是笼统 BBR，而是：

`CFBR = collision-forced benign denials / model-benign events`

同时报告分子分母，避免小事件域产生夸张百分比。

### RQ3：观测精化是否消除碰撞所迫的拒绝？

固定 `M,B,E`，比较 `O_ctx` 与 `O_event`：

- mixed observation classes；
- collision-forced benign events；
- 保持危险事件全部拒绝时的良性完成数。

不得在横向比较中同时修改模型粒度。当前 31 个可建模候选中，14 个 `O_ctx` 正例在 `O_event` 下均降为 0。

### RQ4：检测是否只是结构启发式的产物？

用两个随机负样本层报告新增候选、误漏类型和未支持节点。该 RQ 不必为每个负样本建立完整状态空间；发现可信候选后再按统一协议建模。

## 对照与 guard

至少比较三种：

1. 当前/手写 guard（如有）：测 guard-induced avoidable denial。
2. 在 `O_ctx` 下最大许可的安全 controller：其 benign denial 按理论应全部为 collision-forced，用来确认归因实现。
3. DirectSAGE/event-taint guard：验证危险事件仍拒绝、碰撞所迫的良性拒绝是否消失。

黑名单可以保留为弱对照，但不能承担最近邻工作比较。此实验的核心不是证明 DirectSAGE 在所有任务上 BBR 最低，而是解释不同 guard 的 benign denials 为什么发生、哪些能靠规则修复。

## 结果表建议

主文一张表即可：

| Workflow group | #templates | #distinct structures | dangerous events | benign events | ctx collision-forced | event collision-forced | avoidable denials |
|---|---:|---:|---:|---:|---:|---:|---:|

再放两个 witness：

- 一个独立附件/模板在 AI 之后进入 sink 的正例；
- 一个 AI 已读取同源内容、因此无碰撞的严格负例。

补充材料提供 38 个候选的逐项状态、100--130 个随机负样本的审计表、契约、策略依据、哈希和反例轨迹。

## 论文中最关键的叙事句

> Verification and synthesis can eliminate guard mistakes only after the runtime observation is fixed. When a model-benign event shares its observation with a model-dangerous event, every safe controller over that interface must deny both. SAGE therefore attributes benign blocking before attempting repair: it separates collision-forced denials, which require additional runtime evidence, from avoidable guard denials, which verification and synthesis can remove.

这句话把验证、合成和信息损失连成一条主线，同时将模型确认清楚地留在本文边界之外。
