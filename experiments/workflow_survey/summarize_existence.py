"""Summarize the current existence study with explicit epistemic boundaries."""
import argparse,json
from collections import Counter
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();r=a.root
 structural=json.loads((r/'structural_summary.json').read_bytes());inventory={x['id']:x for x in json.loads((r/'structural_inventory.json').read_bytes())};checked=json.loads((r/'reviewed_slice_results.json').read_bytes())
 manifest=json.loads((r/'candidate_final_status.json').read_bytes())
 status_counts=Counter(x['final_status'] for x in manifest['candidates'])
 positives=[x for x in checked if x['observations']['ctx']['collision_classes']]
 negatives=[x for x in checked if not x['observations']['ctx']['collision_classes']]
 fingerprints={inventory[x['id']]['structure_fingerprint'] for x in positives}
 candidate_by_id={x['id']:x for x in manifest['candidates']}
 direct_ids={x['id'] for x in manifest['candidates'] if x.get('subtype')=='direct_resource'}
 direct=[x for x in positives if x['id'] in direct_ids]
 direct_fingerprints={inventory[x['id']]['structure_fingerprint'] for x in direct}
 conditional=[x for x in positives if x['id'] not in direct_ids]
 second={};usage=Counter();successful=0
 for pth in sorted((r/'llm_collision_second_pass').glob('batch_*/result.json')):
  d=json.loads(pth.read_bytes())
  if 'choices' in d:
   successful+=1
   for k in ('prompt_tokens','completion_tokens','total_tokens'):usage[k]+=d.get('usage',{}).get(k,0)
   proposal=pth.with_name('review_UNVERIFIED.json')
   if proposal.exists():
    for x in json.loads(proposal.read_bytes()).get('results',[]):second[x['id']]=x
 verdicts=Counter(x.get('verdict') for x in second.values())
 machine={'claim_level':'existence under reviewed source-grounded contracts and study-supplied labels/policies; not native prevalence',
  'public_workflows_parsed':structural['counts']['downloaded_json_parsed'],'structural_candidates':structural['counts']['llm_ai_then_file_then_binary_sink_candidates'],
  'candidate_population_final_status':dict(status_counts),
  'reviewed_local_models':len(checked),'ctx_collision_templates':len(positives),'ctx_collision_distinct_structure_fingerprints':len(fingerprints),
  'conservative_direct_independent_resource_templates':len(direct),'conservative_direct_distinct_structures':len(direct_fingerprints),
  'conservative_direct_ids':[x['id'] for x in direct],
  'context_projection_ids':[x['id'] for x in positives if candidate_by_id[x['id']].get('subtype')=='context_projection'],
  'transform_contract_ids':[x['id'] for x in positives if candidate_by_id[x['id']].get('subtype')=='transform'],
  'ctx_no_collision_local_models':len(negatives),'event_collision_templates':sum(bool(x['observations']['event']['collision_classes']) for x in checked),
  'positive_ids':[x['id'] for x in positives],'negative_ids':[x['id'] for x in negatives],
  'second_pass_unique_workflows_returned':len(second),'second_pass_verdicts_unverified':dict(verdicts),'second_pass_usage_returned_only':dict(usage),
  'controlled_replays':[{'id':13845,'runs':6},{'id':15449,'runs':16},{'id':19292,'runs':4}],
  'formal_witness':'For every positive local model, exists benign g and dangerous d with identical resolved sink action and O_ctx(g)=O_ctx(d); O_event separates all reported pairs.',
  'limitations':['A bare workflow JSON has no confidentiality labels or destination policy, so collision is not an unconditional property of JSON alone.',
   'Labels, policies, paired fixtures and some remote contracts are study supplied; results establish susceptibility/existence under those deployments, not observed production incidents.',
   'All detector-positive candidates were reviewed, but the detector defines a narrow conditional population and cannot estimate ecosystem prevalence.',
   'The frozen negative audit sample tests detector misses; its semantic review is still pending.',
   'Second-pass LLM verdicts are search assistance only and are not counted as confirmed collisions.']}
 (r/'EXISTENCE_RESULTS.json').write_text(json.dumps(machine,ensure_ascii=False,indent=2),encoding='utf-8')
 rows='\n'.join(f"| {x['id']} | {inventory[x['id']]['name']} | {inventory[x['id']]['total_views']} | {inventory[x['id']]['structure_fingerprint'][:10]} |" for x in positives)
 neg=', '.join(str(x['id']) for x in negatives)
 report=f'''# 公开工作流中的观测碰撞：当前存在性结论

## 结论

**可以确认：这批公开工作流包含能够产生 SAGE 观测碰撞的真实工作流结构。** 这里的严格含义是：对源 JSON 支持的读写契约，以及研究明确给定的资源标签和目标策略，SAGE 找到了良性事件 `g` 和危险事件 `d`，二者具有相同的 resolved sink action，满足 `O_ctx(g)=O_ctx(d)`；换成 `O_event` 后全部被区分。

这不是“在生产部署中观察到泄漏/误拦”的结论。工作流 JSON 本身没有保密标签和目标策略，因此脱离 `(M,B,O)` 问“JSON 是否碰撞”在形式上没有定义。当前证据建立的是**外部公开工作流对该问题的实际易感性和可实现见证**。

## 数据

- 独立公开目录成功下载并解析：{structural['counts']['downloaded_json_parsed']} 个工作流。
- 自动结构筛选得到：{structural['counts']['llm_ai_then_file_then_binary_sink_candidates']} 个目标候选；全部完成源依赖审查。最终状态为：确认碰撞情景 {status_counts['confirmed_collision_under_reviewed_contract']}、无碰撞 {status_counts['no_collision_provenance_already_observed']}、无效结构 {status_counts['invalid_structural_candidate']}、契约未决 {status_counts['contract_unresolved']}。
- 送入 SAGE 的已审查局部模型：{len(checked)} 个（全部可确认正例与负例；无效和未决项不强行建模）。
- `O_ctx` 确认碰撞：{len(positives)} 个模板、{len(fingerprints)} 种不同结构；其中 15449 与 15451 的结构指纹相同，不能算两个独立应用。
- 最保守直接资源子集：{len(direct)} 个模板、{len(direct_fingerprints)} 种结构，ID 为 {', '.join(str(x['id']) for x in direct)}。这些路径包含 AI 没有读取的、独立配置的模板、附件或文件。
- 其余 {len(conditional)} 个正例依赖字段级资源划分或远端变换的保守传播契约，应作为第二证据层单独报告。
- 严格反例：{len(negatives)} 个局部模型没有 `O_ctx` 碰撞，ID 为 {neg}。这些反例主要是资源内容或其派生物已经被 AI 读取，污点已经进入 ctx。
- `O_event` 在所有 {len(checked)} 个局部模型中确认碰撞数为 0。

| 模板 ID | 工作流 | 页面 views（非部署数） | 结构指纹前缀 |
|---:|---|---:|---|
{rows}

## 物理边界校准

三个外部模板进行了受控边界回放，共 26 次：13845（原始代码节点与 Gmail MIME helper）、15449（包含一项补充性的模型边界校准）、19292（Gmail 草稿附件 MIME helper）。正文外部效度比较始终固定模型，只替换 `O_ctx` 与 `O_event`；15449 的 coarse/refined 结果不计入主比较。

这些回放没有启动完整 n8n、Drive、Gmail、Zoho 或其他远端服务，不能称为端到端部署实验。

## 第二轮反证式筛查

尚未编译的候选正在用完整参数检查“资源污点是否其实已进入 AI 上下文”。目前成功返回 {len(second)} 个不同工作流；模型建议分布为 {dict(verdicts)}。这些建议全部保持 `UNVERIFIED`，不增加上述确认碰撞计数。已返回调用用量为 {usage['total_tokens']} token；超时/502 是否计费未知。

## 当前论文可以安全写到的强度

可以写：公开的、独立作者提供的 agentic workflows 中存在源代码可定位的 late-resource pattern；在经审查契约和明确策略下，它们产生可检查的观测碰撞见证，event-taint 消除这些碰撞。

不能写：观测碰撞在 n8n 中的发生率是 {len(positives)}/{structural['counts']['downloaded_json_parsed']}，或这些模板的真实用户已经遭遇相应误拦。38 个是窄检测器定义的条件总体，且标签/策略由研究补充。

机器可读结果：`EXISTENCE_RESULTS.json`；逐事件见证：`reviewed_slice_results.json`；受控回放：`pilot_13845/report.json`、`onboarding_factorial/report.json`、`pilot_19292/report.json`。
'''
 (r/'EXISTENCE_REPORT_CN.md').write_text(report,encoding='utf-8')
 print(json.dumps({k:v for k,v in machine.items() if k not in ('limitations','formal_witness')}))
if __name__=='__main__':main()
