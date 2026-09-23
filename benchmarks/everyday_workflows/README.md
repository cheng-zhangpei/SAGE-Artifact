# Everyday workflow guard-drafting challenge (v1)

新增挑战集，不修改或替换 `benchmarks/context_invisible` 的原36对。
目标是检查完整 guard 起草中的现实遗漏，同时明确呈现当前形式模型的边界，
不是挑选模型失败样例或保证 SAGE 在所有业务需求上满分。

## 数据组成

- `catalog.yaml` (W01–W12) 与 `extension.yaml` (W13–W36)：36个工作流，每个4对危险/良性探针，共144对、288个事件探针。
- `boundaries.yaml`：6个边界场景，每个2个对照探针，共12个业务需求探针。
- `implicit_flows.yaml`：12个真实隐式流与侧信道压力题，单独作为当前后端不支持的能力边界。
- 数据集包含54个场景、300个显式探针，以及12个隐式流压力题。只有144对属于当前 union-flow 可执行评测。
- 旧集加本扩展共有180对可执行事件探针；旧 runner 不会自动发现这个独立目录。
- 场景均为人工构造的现实业务原型，不声称来自生产日志。

### 72-task authoring benchmark layout

The authoring benchmark has two explicitly separated layers:

- Base layer: W01--W36, 36 compact workflow-level drafting tasks.
- Composition layer: 6 business-family clusters x 6 nested dispatch counts
  (8/16/24/32/40/48), yielding 36 additional drafting tasks.

Together these are 72 workflow-level model calls. The six levels within each
composition family are correlated prefixes, so the composition layer has six
business-family clusters rather than 36 independent domains. Counts and the
SHA256 ordering are frozen independently of model outcomes. Generate and check
the composition layer with:

```powershell
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.composition_suite validate
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.composition_suite export --output benchmarks/everyday_workflows/composition_cases
```

| 工作流 | 业务 | 易遗漏之处 |
| --- | --- | --- |
| W01 | 客服回复 | 完整附件、第三方诊断副写入、追加不清除 |
| W02 | 月度工资 | 目标标签不同、税务抄送公开公告 |
| W03 | 产物发布 | 完整性和机密性方向不同、外部日志 |
| W04 | 门诊通知 | 同次查询病历、日历镜像 |
| W05 | 法务摘要 | 多跳共享笔记、独立邮件出口 |
| W06 | 差旅申请 | 身份与支付卡的不同接收边界 |
| W07 | 电商退款 | 同名工具跨 Agent、现场生成令牌 |
| W08 | 运维排障 | 配置凭据、远程副本、临时凭据 |
| W09 | 采购下单 | 不可信网页与内部底价的交错约束 |
| W10 | 教务通知 | 新生成成绩、身份核对不等于成绩授权 |
| W11 | 跨租户支持 | 共享摘要积累、工具内部回退检索 |
| W12 | 事件交接 | 两跳传播、附件与独立公开标题 |

## 给模型什么

只使用 `dataset.drafting_input(workflow)` 返回的白名单输入：
场景自然语言说明、标签含义、每个具体调用的 agent/tool/params 和自然语言描述、明确的 B(v)。
这是原 Config A 类型的输入；新集不设置 A/C 对照。
不得把整个 catalog 发给模型：其中有后端 `reads/writes/gen`、探针及标准答案。
自然语言明确写出全部输入、输出、副写入、生成信息和初始条件，不靠隐瞒行为制造错误。
输出继续沿用项目 `{"guards":[{"agent":...,"tool":...,"params":...,"forbidden_labels":[...]}]}` 格式。
需要正常提供 guard 的事件标签触发语义与精确参数匹配规则，不要求模型猜测 DSL。

`dataset.scenario_spec(workflow)` 提供可直接交给 `build_scenario` 的后端模型。
标签、禁止目标和动作语义是该构造任务的明确假设，不是 SAGE 自动理解自然语言的结果。
所有初始状态安全；探针从同一工作流初态按 prefix 执行，再检查 target。
prefix 可以为空：这表示共享工作槽尚未收集受限资料，并不表示工具调用不合法。
每对控制一个业务差异；不同 pair 可复用事件，不应把它们视为独立工作流样本。

## 判分及边界

1. 一次起草生成整个工作流的 guard，不能每个探针分别起草。
2. 格式错误、危险漏防、良性误阻断、完整轨迹 FAIL、资源超限 UNKNOWN 分开记录。
3. 探针对只是诊断。完整轨迹验证调用现有 shortest_counterexample；不能以288个事件全对冒充轨迹证明。
4. 保存所有模型原始回答和成功结果，包括强模型全对；不得按结果删除题目。
5. 固定模型版本、提示词、重复次数、资源预算并冻结数据后再跑。此版未经模型试跑或难度筛选。
6. 36个工作流是36个起草任务；4对探针和多次重复不能伪装成更多独立业务样本。不同业务可能复用相同机制，不能声称有36种独立冲突机制。

边界部分单独报告，不进入 union-flow 的安全通过率分母：
L01认证解密、L02强更新可能导致保守误阻断；L03需要外部策略更新；
L04检查提交竞态违反抽象模拟条件；L05活性、L06隐式流不是当前禁止流不变量能保证的性质。
这些是明确的业务标准与能力假设分析，目前没有实现物理回放，不能声称已实测 SAGE 失败。
也不能将“不支持”计为成功。未来实现适配器或可信解密扩展时应重新评估，不能永久硬编码失败。

隐式流压力题位于 `implicit_flows.yaml`，不伪装成当前 SAGE 已支持的事件题。
它们覆盖分支选择、错误码、结果数量、排序、调度顺序、响应延迟、接收者选择、
重试次数、公开验证反馈和缓存时序。它们的共同判定是业务上应禁止，但当前后端明确
返回 `UNSUPPORTED_PROPERTY`，因为秘密影响了控制流、输出选择、时序或其他侧信道，
而不是显式标签到写入位置的 union-flow。未来若扩展非干扰、隐式流或侧信道模型，
应把这些题转换为真正可执行的三值验证，而不是修改现有 oracle。

可单独运行 `gpt-5.5` 隐式流识别压测：

```powershell
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.implicit_run --model gpt-5.5 --output output/implicit_gpt55.jsonl
```

这不是普通 guard 起草实验。模型只判断业务上是否应 `DENY`，不能输出 SAGE guard；
输出回答仍然只给故事、秘密名称和可观察通道，不给 `UNSUPPORTED_PROPERTY` 或后端语义。
结果按业务 oracle 统计，但 `sage_verdict` 固定为 `NOT_APPLICABLE`，不混入显式流指标。

## 离线校验

在仓库根目录运行：

```powershell
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.validate
```

校验器检查ID/动作唯一性、安全初态、可执行且安全的prefix、手写危险/良性预期、
DirectSAGE判定，以及每个完整工作流无guard存在反例、有编译guard无可达违反。
资源上限20000状态，超限直接失败而不记为PASS。
标准答案先在数据中人工声明，再以状态执行核对；这仍复用了 SAGE 转移实现，
不是独立实现的形式正确性证明，也不替代自然语言与模型的一致性人工审查。

该模块不访问网络、不使用API密钥、不运行LLM，不更改现有实验入口。

## 起草与候选评估入口

当前协议为 `config-a-v2-no-formal-hints-one-shot`：系统提示仅给任务、输出格式和
guard字段的使用约定，不给事件标签并集公式、读写集合、编译算法或副写入检查提示。
场景中的追加存储和工具行为仍保留，属于必要业务说明。此前3题pilot的提示含
事件标签定义，必须单列，不能并入本协议结果。所有36题在新协议下重新起草。

下面三个命令完全离线，输出为新建的JSONL文件，已有文件不会覆盖：

```powershell
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.run prompts --output output/everyday_prompts.jsonl
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.run direct --output output/everyday_direct.jsonl
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.run evaluate --candidates candidates.jsonl --output output/everyday_evaluation.jsonl
```

候选文件每行格式为 `{"workflow":"W01","raw_content":"{\"guards\":[]}"}`。
解析不提取Markdown、不修补截断JSON，拒绝重复键、非JSON数值、未声明标签和不存在的具体调用。
结果区分 FORMAT_ERROR、轨迹 PASS/FAIL/UNKNOWN，并返回最短违反轨迹。
`probe_der`、`probe_bbr`只在手写固定探针域计算，不是所有可达事件的DER/BBR。
即使候选阻断了探针的上游步骤，仍独立评估该目标事件，并另记录被阻断的前缀；
因此事件漏防与完整轨迹安全可能不同，不能相互替代。

联网仅在显式使用 `live` 时发生。通过当前进程环境设置 `SAGE_API_KEY` 和
`SAGE_API_BASE_URL`（OpenAI兼容API根，例如 `https://provider.example/v1`）；不要把密钥写入文件。
必须指定真实的服务商模型ID：

```powershell
.venv/Scripts/python.exe -B -m benchmarks.everyday_workflows.run live --model YOUR_MODEL_ID --workflow W01 W15 W36 --repetitions 1 --output output/everyday_live.jsonl
```

每个工作流每次重复仅请求一次，不重试、不追加自评提示。API失败记录后停止；
截断回复保留原文并标为TRUNCATED，不作为有效候选。成功和失败均逐条写入并刷新。
输出保存完整提示词、原回复、finish_reason、token用量、模型标识、源文件哈希和验证结果。
manifest中的repetitions只控制live模式，direct和prompts每个工作流输出一次。
边界场景仍为NOT_IMPLEMENTED，不参与该入口的可执行统计。

运行入口测试（只使用模拟网络，不消耗API）：

```powershell
.venv/Scripts/python.exe -B -m unittest benchmarks.everyday_workflows.test_evaluate
```
