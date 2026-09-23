# SAGE 外部工作流实验设计：区分模型损失、观测损失与规则错误

## 1. 要回答的核心问题

外部实验不直接宣称“公开工作流原生具有某种保密策略”。它回答三个逐层问题：

1. 公开 agentic workflows 是否包含这样的执行结构：安全相关资源进入当前 sink event，但没有进入 agent context？
2. 在固定模型、策略和事件域时，context-only observation 是否把模型已经区分的良性/危险事件合并，event-taint 是否能消除这些碰撞？
3. 哪些候选因为来源 provenance 已经进入 context 而不形成碰撞，从而划清观测分析的适用边界？

这对应信息损失链：

`concrete execution --alpha--> model event (x,u,eta) --O--> guard input --g--> decision`

- `alpha` 合并了安全性不同的具体执行：模型损失，需模型精化。
- 模型事件不同，但 `O` 将良性/危险事件映到同一输入：观测损失，需观测精化。
- 模型和观测足以区分，已有 guard 仍多拦或漏拦：规则错误，适合验证、反例和合成。

因此，观测分析不是验证/合成之外的第二项功能；它回答安全且宽松的 guard 在当前接口上是否可实现。

形式上，令模型事件域为 `E`、危险事件为 `D`、良性事件为 `G=E\D`。当且仅当存在

`g in G, d in D: O(g)=O(d)`

时，任何基于 `O` 的事件安全无记忆控制器都必须连同 `d` 一起拒绝 `g`。这就是碰撞所迫的 benign blocking。

## 2. 数据集和筛选漏斗

保留完整漏斗，不能以 8/10,892 报发生率：

1. 当前公开 n8n 目录：12,224 个唯一 ID。
2. 免费且可下载：10,921 个；成功下载解析 10,892 个，失败 29 个。
3. 识别到 LLM 节点：5,707 个。
4. 含二进制 sink 候选：226 个。
5. 窄规则识别“AI 后仍读文件并送往二进制 sink”：38 个。
6. 38 个候选全部完成源依赖审查：14 个确认碰撞情景、17 个无碰撞、6 个结构无效、1 个契约未决；31 个可确认项均进入 SAGE 局部模型。

38 个是检测器定义的候选全集，不是所有可能碰撞的全集。全审查可以估计该窄检测器候选集内的确认率，但不能估计总体 prevalence。

## 3. 研究策略族，避免逐例编造政策

对适用工作流使用预先固定的策略族，而不是看完结果后为每个模板定制：

- `private-source -> external-recipient/public-channel`：私有 Drive、mailbox、tenant storage 的资源不得进入外部邮件、公开社交渠道或跨租户目标。
- `recipient-scoped -> different-recipient`：仅授权给指定主体的附件不得发往另一主体。
- `internal-template -> prospect/customer`：内部模板中被标为不可披露的部分不得进入发给 prospect/customer 的产物。

每个模板记录策略是否适用、来源身份、sink 身份、依据来自原始配置还是研究 fixture。不适用记为 `policy_not_applicable`，不能强行产生危险事件。

存在性主实验采用成对 perturbation：保持 agent context、resolved sink action 和非目标资源固定，只将独立 late resource 在 `public/restricted` 标签和相应 fixture 之间切换。这测量工作流对观测损失的 susceptibility，不冒充生产事件频率。

## 4. 固定模型的观测干预

正文比较始终固定模型 `M`、策略 `B`、事件域 `E`、resolved actions 和 paired fixtures，只替换 observation：

- `O_ctx` 是否把模型已经区分的良性/危险事件映到同一 guard input；
- `O_event` 是否分开相同事件对；
- DirectSAGE 是否在维持危险事件拒绝的同时释放被碰撞牵连的良性事件。

因此这轮实验测量的是观测精化，不测量模型精化。`alpha` 造成的模型损失仍是理论链条中的上游边界：如果安全差异在进入模型前已经消失，SAGE 不能通过修改 observation 或 guard 恢复它。模板 15449 已有的 coarse/refined 四格只保留为补充性的边界校准，不计入正文外部效度数字。

## 5. 批量归因算法

对每个模型一次性枚举/探索事件域，按 observation key 分组：

1. `e in G` 被安全控制器拒绝，且同组含 `d in D`：`observation_collision`。
2. concrete oracle 判允许，但 `e in D`：`model_induced_blocking`。
3. `e in G`，同组不含危险事件，部署 guard 仍拒绝：`guard_extra_denial`。
4. 事件域不完整且未找到危险同伴：`no_collision_found_domain_incomplete`，不能写成无碰撞。
5. 无独立 concrete oracle：模型危险事件记为 `concrete_unknown`，不能自动归入模型精化。

所有结果输出相同 resolved action 的良性/危险 witness、原始节点和参数证据、模型与策略版本、域覆盖状态。

## 6. 主要指标

### 存在性与适用范围

- 可下载、可解析、LLM、binary sink、late-resource 各阶段数量。
- `modeled / candidate` 覆盖率及未建模原因。
- 确认碰撞模板数和去重结构数。
- 策略不适用、无独立资源、资源 provenance 已进 ctx、契约不足、无效结构的数量。

### 观测精化

- `O_ctx` collision classes 和被迫拒绝的 benign events。
- `O_event` 对同一模型/域的 collision classes。
- `collision elimination = collisions_ctx - collisions_event`。
- 保持危险事件全部拒绝时，良性完成数的变化。

### 自动化与验证

- DirectSAGE 规则数、合成时间和验证结果。
- 空 guard / 手写 guard 的反例类型。
- 合成 guard 的额外拒绝数；对于固定有限域，最大许可结果应为 0，需作为理论确认而非性能胜出宣传。

## 7. 当前结果的证据层级

### 最保守存在性子集

- 7 个模板包含 AI 未读取的独立模板、附件或文件，对应 6 种结构。
- 5 个模板的最终产物包含被 AI prompt 投影掉的字段，称为 `context_projection`，不称为模型精化。
- 2 个模板依赖远端变换保持来源 provenance，单独报告其契约假设。

38 个候选最终得到 14 个确认碰撞情景、17 个无碰撞、6 个无效结构和 1 个契约未决。14 个正例对应 13 种结构；17 个负例说明审查不会把所有“AI 后出现新字节”的流程都判成碰撞。

## 8. 可在论文中承担的角色

主文只需一个小型漏斗表、一张固定模型的 `O_ctx`/`O_event` 结果表和两个 witness。其余逐工作流契约、失败原因、模型输入输出、哈希与回放日志放补充材料。

这项实验支持的主张是：

> Partial observation is a deployment boundary for guard synthesis. Public agentic workflows repeatedly contain late-bound resources whose security labels affect a sink event without being represented in the agent context. Under source-reviewed contracts and explicit policy scenarios, these workflows yield checkable context-observation collisions; event-taint separates the witnesses.

不能支持总体发生率或真实生产事故主张，除非以后获得原生标签、部署策略和运行 trace。

## 9. 下一步执行顺序

1. 语义审查固定种子抽取的 100 个 detector-negative，估计窄检测器遗漏的结构类型。
2. 正文只报告固定模型下 `O_ctx` 到 `O_event` 的变化；模型边界校准放补充材料。
3. 从 14 个正例中选择一个直接资源案例和一个 context-projection 案例作为正文 witness。
4. 将 38 个候选的逐项证据、无效原因和契约假设放入补充材料。
