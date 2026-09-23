"""Conservative structural inventory; structural flags are NOT SAGE collisions."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

REF = re.compile(r'''\$\(\s*['"]([^'"]+)['"]\s*\)|\$node\[\s*['"]([^'"]+)['"]\s*\]''')
AI = re.compile(r'(?:\.agent$|\.chain\w*|\.openAi$|\.googleGemini$|\.informationExtractor$|\.textClassifier$|\.sentimentAnalysis$|\.summarizationChain$)', re.I)
CHANNELS = ('gmail', 'emailsend', 'slack', 'telegram', 'whatsapp', 'microsoftoutlook', 'discord', 'twitter', 'linkedin', 'youtube', 'facebookgraphapi')

def text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def reach(edges, start):
    pending, seen = list(edges.get(start, ())), set()
    while pending:
        node = pending.pop()
        if node not in seen:
            seen.add(node)
            pending.extend(edges.get(node, ()))
    return seen

def has_binary_config(params):
    if isinstance(params, dict):
        for key, val in params.items():
            if key.lower() in ('attachmentsui', 'attachmentsbinary', 'binarypropertyname', 'inputdatafieldname', 'binaryfieldname') and val:
                return True
            if key.lower() in ('binarydata', 'sendbinarydata') and val is True:
                return True
            if has_binary_config(val):
                return True
    elif isinstance(params, list):
        return any(has_binary_config(x) for x in params)
    return False

def inspect_document(document, file_hash):
    meta = document['workflow']
    w = meta['workflow']
    nodes = w.get('nodes', [])
    counts = Counter(n.get('name') for n in nodes)
    duplicates = sorted(str(k) for k,v in counts.items() if v > 1)
    named = {n['name']: n for n in nodes if isinstance(n.get('name'), str)}
    edges = {name: set() for name in named}
    references = {name: set() for name in named}
    invalid = []
    for origin, ports in (w.get('connections') or {}).items():
        if not isinstance(ports, dict):
            invalid.append({'from': origin, 'unsupported_connection_schema': type(ports).__name__})
            continue
        for group in (ports or {}).get('main', []) or []:
            for edge in group or []:
                target = edge.get('node')
                if origin in named and target in named:
                    edges[origin].add(target)
                else:
                    invalid.append({'from':origin,'to':target})
    for name, node in named.items():
        for match in REF.finditer(text(node.get('parameters', {}))):
            source = match.group(1) or match.group(2)
            if source in named:
                references[name].add(source)
            else:
                invalid.append({'expression_in':name,'reference':source})
    descendants = {name: reach(edges, name) for name in named}
    ai, sinks, files, code, binary_sinks = [], [], [], [], []
    for name, node in named.items():
        typ = node.get('type', '')
        params = node.get('parameters', {})
        low = typ.lower()
        operation = str(params.get('operation', '')).lower()
        if AI.search(typ):
            ai.append(name)
        if low.endswith(('.code', '.function', '.functionitem')):
            code.append(name)
        if any(channel in low for channel in CHANNELS) and 'trigger' not in low:
            if operation in ('send', 'reply', 'sendandwait', 'post', 'create', 'upload', ''):
                sinks.append(name)
        if any(channel in low for channel in ('googledrive', 'awss3', 'dropbox', 'ftp', 'onedrive')) and operation in ('upload', 'create', 'copy', 'share', ''):
            sinks.append(name)
        if name in sinks and has_binary_config(params):
            binary_sinks.append(name)
        if operation in ('download', 'getattachment') or (params.get('options') or {}).get('downloadAttachments') is True:
            files.append(name)
        if 'httprequest' in low and re.search(r'"responseFormat"\s*:\s*"file"', text(params)):
            files.append(name)
    auxiliary_ai = [n['name'] for n in nodes if '.lmChat' in n.get('type','') or '.embeddings' in n.get('type','')]
    late_paths = []
    for source in files:
        upstream_ai = [a for a in ai if source in descendants[a]]
        for sink in binary_sinks:
            if sink not in descendants[source]:
                continue
            between = descendants[source] & {n for n in named if sink in descendants[n] or n == sink}
            late_paths.append({'file_source':source, 'binary_sink':sink,
                              'earlier_ai_nodes':upstream_ai,
                              'intervening_ai_nodes':sorted(set(ai)&between),
                              'code_nodes_on_path':sorted(set(code)&between),
                              'status':'structural_candidate_requires_contract_review'})
    connected = set(edges)
    main_edges = sum(map(len, edges.values()))
    node_types = sorted(n.get('type','') for n in nodes if 'stickyNote' not in n.get('type',''))
    normalized = {'types':node_types,'edges':sorted((named[a].get('type'), named[b].get('type')) for a in edges for b in edges[a])}
    return {'id':meta['id'],'name':meta['name'],'author':meta.get('user',{}).get('username'),
            'total_views':meta.get('totalViews'),'recent_views':meta.get('recentViews'),
            'source_sha256':file_hash,'node_count':len(nodes),'main_edges':main_edges,
            'llm_related':bool(ai or auxiliary_ai),'main_ai_nodes':ai,'auxiliary_ai_nodes':auxiliary_ai,
            'external_action_candidates':sorted(set(sinks)), 'binary_sink_candidates':binary_sinks,
            'explicit_file_sources':files,'late_file_paths':late_paths,'code_nodes':code,
            'duplicate_names':duplicates,'unresolved_references':invalid,
            'has_main_cycle':any(name in descendants[name] for name in named),
            'explicit_cross_node_reference_count':sum(map(len,references.values())),
            'structure_fingerprint':hashlib.sha256(text(normalized).encode()).hexdigest(),
            'sage_status':'not_modeled', 'runtime_status':'not_executed'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    rows, errors=[],[]
    for path in sorted((args.root/'workflows').glob('*.json')):
        try:
            raw=path.read_bytes()
            rows.append(inspect_document(json.loads(raw),hashlib.sha256(raw).hexdigest()))
        except Exception as e:
            errors.append({'file':path.name,'error':str(e)[:200]})
    llm=[x for x in rows if x['llm_related']]
    patterns=[x for x in llm if any(p['earlier_ai_nodes'] and not p['intervening_ai_nodes'] for p in x['late_file_paths'])]
    counts={'downloaded_json_parsed':len(rows),'parse_errors':len(errors),'llm_related_by_node_type':len(llm),
            'llm_with_external_action_candidates':sum(bool(x['external_action_candidates']) for x in llm),
            'llm_with_binary_sink_candidates':sum(bool(x['binary_sink_candidates']) for x in llm),
            'llm_with_code_nodes':sum(bool(x['code_nodes']) for x in llm),
            'llm_with_main_cycles':sum(x['has_main_cycle'] for x in llm),
            'llm_with_unresolved_references':sum(bool(x['unresolved_references'] or x['duplicate_names']) for x in llm),
            'llm_ai_then_file_then_binary_sink_candidates':len(patterns),
            'confirmed_sage_collisions_in_this_corpus':None}
    report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'counts':counts,
            'limitations':['Node-type heuristic; custom HTTP LLM calls may be missed.',
                          'Default operations require node-version review; external-action candidates are not verified sinks.',
                          'Main graph reachability is not data dependency or runtime reachability.',
                          'No labels, contracts or safety policies inferred from titles or popularity.',
                          'Structure fingerprints flag review candidates, not authoritative semantic deduplication.',
                          'Views are exposure metadata, not deployment counts.'],
            'errors':errors,'structural_candidates':patterns}
    (args.root/'structural_inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.root/'structural_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(counts),flush=True)

if __name__=='__main__':
    main()
