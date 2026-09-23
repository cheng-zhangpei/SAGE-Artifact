# 公开工作流中的观测碰撞：当前存在性结论

## 结论

**可以确认：这批公开工作流包含能够产生 SAGE 观测碰撞的真实工作流结构。** 这里的严格含义是：对源 JSON 支持的读写契约，以及研究明确给定的资源标签和目标策略，SAGE 找到了良性事件 `g` 和危险事件 `d`，二者具有相同的 resolved sink action，满足 `O_ctx(g)=O_ctx(d)`；换成 `O_event` 后全部被区分。

这不是“在生产部署中观察到泄漏/误拦”的结论。工作流 JSON 本身没有保密标签和目标策略，因此脱离 `(M,B,O)` 问“JSON 是否碰撞”在形式上没有定义。当前证据建立的是**外部公开工作流对该问题的实际易感性和可实现见证**。

## 数据

- 独立公开目录成功下载并解析：10892 个工作流。
- 自动结构筛选得到：38 个目标候选；全部完成源依赖审查。最终状态为：确认碰撞情景 14、无碰撞 17、无效结构 6、契约未决 1。
- 送入 SAGE 的已审查局部模型：31 个（全部可确认正例与负例；无效和未决项不强行建模）。
- `O_ctx` 确认碰撞：14 个模板、13 种不同结构；其中 15449 与 15451 的结构指纹相同，不能算两个独立应用。
- 最保守直接资源子集：7 个模板、6 种结构，ID 为 8104, 11529, 14185, 14717, 15449, 15451, 19292。这些路径包含 AI 没有读取的、独立配置的模板、附件或文件。
- 其余 7 个正例依赖字段级资源划分或远端变换的保守传播契约，应作为第二证据层单独报告。
- 严格反例：17 个局部模型没有 `O_ctx` 碰撞，ID 为 7201, 7695, 9146, 10441, 10880, 11912, 12959, 13237, 13659, 15440, 16375, 16881, 17351, 17933, 18142, 18341, 18417。这些反例主要是资源内容或其派生物已经被 AI 读取，污点已经进入 ctx。
- `O_event` 在所有 31 个局部模型中确认碰撞数为 0。

| 模板 ID | 工作流 | 页面 views（非部署数） | 结构指纹前缀 |
|---:|---|---:|---|
| 6531 | LinkedIn content creator system | 17712 | 42920485cd |
| 8104 | Generate AI-powered sales proposals from JotForm leads with OpenAI and Google Docs | 332 | 309e0fe032 |
| 10126 | Automate YouTube thumbnail creation & social publishing with Templated.io & Blotato | 3134 | a49fe1be8f |
| 11529 | Organize school emails with AI, Google Calendar and Drive auto-triage system | 334 | 3f220c5e02 |
| 11745 | Generate employee performance review summaries with GPT-4, Gmail and Sheets | 100 | c465c97d3c |
| 12731 | Grade and deliver multi-course assignment feedback with GPT-4o, Google Drive, Slack, and Gmail | 54 | 4b53980a5c |
| 14185 | Generate and Send Personalized Quotations PDF  | 391 | b147b56539 |
| 14717 | Create AI proposals from Fireflies transcripts with GPT-4o, Google Docs, Gmail and Telegram approval | 29 | 6416d49da1 |
| 15449 | Automate employee onboarding with Groq, Gmail, Slack and Google Workspace | 31 | 693ac76c54 |
| 15451 | Automate AI-powered employee onboarding emails and Slack updates with Groq, Gmail, and Google Sheets | 45 | 693ac76c54 |
| 16217 | Send weekly Facebook and Instagram PDF performance reports with Gemini and Gmail | 14 | af65e206e1 |
| 18053 | Send weekly Meta Ads performance PDF reports with Gemini and Gmail | 1 | 149792f36a |
| 18673 | Send daily CFO invoice health reports with Google Sheets, Groq, Gmail and Slack | 0 | 7db3f4534d |
| 19292 | Create Gmail drafts from business cards with Google Drive, Gemini, Slack and Discord | 0 | 56dbd128f5 |

## 物理边界校准

三个外部模板进行了受控边界回放，共 26 次：13845（原始代码节点与 Gmail MIME helper）、15449（包含一项补充性的模型边界校准）、19292（Gmail 草稿附件 MIME helper）。正文外部效度比较始终固定模型，只替换 `O_ctx` 与 `O_event`；15449 的 coarse/refined 结果不计入主比较。

这些回放没有启动完整 n8n、Drive、Gmail、Zoho 或其他远端服务，不能称为端到端部署实验。

## 第二轮反证式筛查

尚未编译的候选正在用完整参数检查“资源污点是否其实已进入 AI 上下文”。目前成功返回 28 个不同工作流；模型建议分布为 {'independent_late_resource': 18, 'invalid_structural_candidate': 6, 'uncertain': 1, 'source_provenance_already_in_ai_context': 3}。这些建议全部保持 `UNVERIFIED`，不增加上述确认碰撞计数。已返回调用用量为 267063 token；超时/502 是否计费未知。

## 当前论文可以安全写到的强度

可以写：公开的、独立作者提供的 agentic workflows 中存在源代码可定位的 late-resource pattern；在经审查契约和明确策略下，它们产生可检查的观测碰撞见证，event-taint 消除这些碰撞。

不能写：观测碰撞在 n8n 中的发生率是 14/10892，或这些模板的真实用户已经遭遇相应误拦。38 个是窄检测器定义的条件总体，且标签/策略由研究补充。

机器可读结果：`EXISTENCE_RESULTS.json`；逐事件见证：`reviewed_slice_results.json`；受控回放：`pilot_13845/report.json`、`onboarding_factorial/report.json`、`pilot_19292/report.json`。
