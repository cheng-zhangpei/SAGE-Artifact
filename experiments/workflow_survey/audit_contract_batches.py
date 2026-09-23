"""Audit API proposal coverage and basic source consistency, never certify semantics."""
import argparse,json
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();base=a.root/'llm_contract_pilot'
    results=[];batches=[];ids=set();usage=Counter()
    inventory={w['id']:w for w in json.loads((a.root/'structural_inventory.json').read_bytes())}
    for response in sorted(base.rglob('result.json')):
        d=json.loads(response.read_bytes());request=response.with_name('request_without_credentials.json')
        if not request.exists():continue
        req=json.loads(request.read_bytes());inputs=json.loads(req['messages'][1]['content']);expected={w['id'] for w in inputs}
        parsed=response.with_name('proposals_UNVERIFIED.json')
        proposals=json.loads(parsed.read_bytes()).get('results',[]) if parsed.exists() else []
        seen={v.get('id') for v in proposals};ids.update(expected)
        for k in ('prompt_tokens','completion_tokens','total_tokens'):usage[k]+=d.get('usage',{}).get(k,0)
        batches.append({'batch':str(response.parent.relative_to(base)),'requested':sorted(expected),'returned':sorted(seen),
                        'missing':sorted(expected-seen),'unexpected':sorted(seen-expected),'http_error':d.get('error_http_status'),
                        'finish_reason':d.get('choices',[{}])[0].get('finish_reason')})
        for proposal in proposals:
            wid=proposal.get('id');issues=[]
            if wid not in expected:issues.append('unexpected_id')
            path=a.root/'workflows'/f'{wid}.json'
            if not path.exists():issues.append('missing_source');nodes={}
            else:nodes={n['name']:n for n in json.loads(path.read_bytes())['workflow']['workflow']['nodes']}
            for key in ('source_node','sink_node'):
                if proposal.get(key) not in nodes:issues.append(key+'_not_exact_source_node')
            if proposal.get('sink_node') not in inventory.get(wid,{}).get('external_action_candidates',[]):
                issues.append('sink_not_in_structural_external_action_candidates_requires_review')
            if proposal.get('full_workflow_supported') and proposal.get('missing_contracts'):
                issues.append('claims_full_support_despite_missing_contracts')
            sink=nodes.get(proposal.get('sink_node'),{})
            if sink.get('type')=='n8n-nodes-base.gmail':
                options=sink.get('parameters',{}).get('options',{})
                if options.get('attachmentsBinary') and not options.get('attachmentsUi'):
                    issues.append('gmail_attachment_config_not_consumed_by_pinned_v2_helper')
            results.append({'id':wid,'proposal_status':proposal.get('status'),'source_node':proposal.get('source_node'),
                            'sink_node':proposal.get('sink_node'),'basic_check_issues':issues,
                            'semantic_status':'unverified','sage_status':'not_compiled_from_proposal',
                            'missing_contracts':proposal.get('missing_contracts',[])})
    out={'requested_unique_workflows':len(ids),'response_batches':len(batches),'usage':dict(usage),
         'proposal_records':len(results),'proposal_status_counts':dict(Counter(x['proposal_status'] for x in results)),
         'records_with_basic_issues':sum(bool(x['basic_check_issues']) for x in results),
         'new_confirmed_collisions':0,'batches':batches,'results':results}
    (base/'BATCH_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 扩大批量试跑结果','',f"已收到 {len(batches)} 批接口结果，涉及 {len(ids)} 个不同工作流。",'',
           '这是契约提取和基本一致性检查，不是这些工作流的 SAGE 全流程执行。', '',
           f"输入 token：{usage['prompt_tokens']}；输出 token：{usage['completion_tokens']}；合计：{usage['total_tokens']}。接口未返回金额。",'',
           '模型建议（按返回记录计，不是工作流占比）：']
    lines += [f'- {k}: {v}' for k,v in out['proposal_status_counts'].items()]
    lines += ['',f"有 {out['records_with_basic_issues']} 条建议被基本一致性检查标记；其余通过基本检查也不等于语义可靠。",'',
              '所有建议保留 unverified 状态。generated_artifact 不能排除独立模板/图片依赖；independent_resource_candidate 不能直接证明碰撞。', '',
              '批次选择：原窄结构候选中未预先建模的 33 个，加上其他二进制发送候选按 ID 排序的前 24 个。不是随机样本，也不能作为总体发生率。原先 9 个不重复调用；新批次使用完整参数。', '',
              '## 独立资源候选与检查标记','', '| ID | 发送节点 | 检查标记 |','|---|---|---|']
    for x in results:
        if x['proposal_status']=='independent_resource_candidate':
            lines.append(f"| {x['id']} | {x['sink_node']} | {', '.join(x['basic_check_issues']) or '基本检查未报错；语义待核验'} |")
    lines += ['', 'binary_012 首次请求发生 TimeoutError，已保留日志并重试一次；首次超时是否扣费未知，以上 token 仅累计已返回用量。',
              '新增确认碰撞数暂为 0，含义是这些新建议尚未被编译验证，绝不表示检测后无碰撞。',
              '全部逐项数据、缺失契约、调用覆盖与错误见 BATCH_AUDIT.json；原始请求和响应在各批次目录。']
    (base/'BATCH_REPORT_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('batches','results')}))

if __name__=='__main__':main()
