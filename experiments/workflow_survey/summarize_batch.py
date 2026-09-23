"""Publish coverage and available attribution without turning missing models into negatives."""
import argparse,json
from collections import Counter
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();r=a.root
    inventory=json.loads((r/'structural_inventory.json').read_bytes())
    summary=json.loads((r/'structural_summary.json').read_bytes())
    checked=json.loads((r/'reviewed_slice_results.json').read_bytes())
    manifest=json.loads((r/'candidate_final_status.json').read_bytes())
    by_id={x['id']:x for x in checked}
    rows=[]
    for w in inventory:
        c=by_id.get(w['id'])
        rows.append({'id':w['id'],'name':w['name'],'llm_related':w['llm_related'],
                     'status':'reviewed_local_model_only' if c else 'not_modeled_no_attribution',
                     'ctx_denials':dict(Counter(x['category'] for x in c['denial_attribution']['ctx'])) if c else None,
                     'event_denials':dict(Counter(x['category'] for x in c['denial_attribution']['event'])) if c else None,
                     'full_workflow_execution':False})
    totals={obs:dict(Counter(x['category'] for c in checked for x in c['denial_attribution'][obs])) for obs in ('ctx','event')}
    report={'counts':summary['counts'],'attributable_local_models':len(checked),'unmodeled_workflows':len(inventory)-len(checked),
            'attribution_totals_selected_model_events_only':totals,
            'limitations':['Selected study-labeled slices; not prevalence or end-to-end benchmark results.',
                          '15449 and 15451 are near-duplicates; not independent applications.',
                          'Model-danger events without an independent concrete oracle remain unknown.',
                          'No collisions found in an unmodeled workflow is never asserted.'], 'workflows':rows}
    (r/'batch_attribution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    c=summary['counts']; lines=[
      '# 批量数据与覆盖范围（2026-09-09）','',
      '**已完成全量下载与结构扫描；尚未完成全量 SAGE 模型接入和执行。**','',
      '原研究 6,003 个工作流归档未取得；以下是独立采集的 n8n 公开目录，不是原论文数据集。','',
      '| 项目 | 数量 |','|---|---:|',
      '| 目录唯一 ID | 12,224 |','| 免费下载目标 | 10,921 |',
      f"| 下载并解析成功 | {c['downloaded_json_parsed']} |",'| 下载失败 | 29 |',
      f"| 含已识别 LLM 节点 | {c['llm_related_by_node_type']} |",
      f"| LLM 工作流含外部动作候选 | {c['llm_with_external_action_candidates']} |",
      f"| LLM 工作流含二进制发送候选 | {c['llm_with_binary_sink_candidates']} |",
      f"| AI 后读文件再发送的结构候选 | {c['llm_ai_then_file_then_binary_sink_candidates']} |",'',
      '结构候选不是已确认碰撞；其余工作流也不能认定无碰撞。', '',
      '## 已有局部模型的批量归因','',
      f"统一归因程序对 {len(checked)} 个可建模候选进行了批量处理；38 个窄候选的最终状态为 {dict(Counter(x['final_status'] for x in manifest['candidates']))}。使用研究设置的标签、策略与有限事件域。", '',
      '| 观测 | 碰撞所迫的良性拦截事件 | 模型判危险、现实判断未知 | 额外守卫误拦 |',
      '|---|---:|---:|---:|']
    for o in ('ctx','event'):
        t=totals[o];lines.append(f"| {o} | {t.get('observation_collision',0)} | {t.get('model_danger_concrete_unknown',0)} | {t.get('guard_extra_denial',0)} |")
    lines += ['',
      '这里使用观测域内最大许可安全决策作对照，因此额外守卫误拦为零是预期性质，不是与现有系统竞争的实测胜出。',
      '模板 15449 和 15451 是同结构近重复，模板数与结构指纹数分别报告。模型危险事件没有现实允许标注，不能全部归入模型精化。', '',
      '## 入职模板的受控校准结果','',
      '模板 15449 的 4 个研究输入、16 次邮件边界回放（原始 Gmail MIME 辅助函数，未启动完整 n8n 或外部服务）：', '',
      '| 模型 / 观测 | 3 个允许操作中完成数 | 1 个禁止操作中拦截数 |',
      '|---|---:|---:|','| 整项 / ctx | 0 | 1 |','| 整项 / event | 2 | 1 |','| 字段 / ctx | 2 | 1 |','| 字段 / event | 3 | 1 |','',
      '这说明统一归因有能力在受控条件下区分两类损失；不能作为全库误拦率。邮件的文档标签与目标策略由研究设置，正文和附件来源分别固定。', '',
      '## 下一批数据的实际缺口','',
      f'当前 {len(inventory)-len(checked)} 个下载工作流没有 SAGE 事件域，统一标为 not_modeled_no_attribution。需要批量转换器及受支持节点的读写契约，之后才能产生所要求的全库拦截归因。',
      '公开 JSON 不提供保密标签和目标策略；模型内碰撞分析可以使用统一声明的研究策略，但结果必须表述为该策略下的分析。模型精化归因还需要独立具体语义依据。',
      '机器可读总表：batch_attribution.json；候选终态：candidate_final_status.json；固定负样本：negative_audit_sample.json；局部模型见证：reviewed_slice_results.json；受控回放：onboarding_factorial/report.json。']
    (r/'REPORT_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'local_models':len(checked),'unknown':len(inventory)-len(checked),'totals':totals}))

if __name__=='__main__':main()
