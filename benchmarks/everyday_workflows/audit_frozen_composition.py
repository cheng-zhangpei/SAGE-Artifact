"""Offline audit of frozen composition drafts; never changes model responses."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from benchmarks.everyday_workflows.composition_suite import build_case, assess_case
from benchmarks.everyday_workflows.evaluate import parse_candidate
from sage.v2.scenario import build_scenario
from sage.v2.coverage import certify_action_coverage
from sage.v2.guards import deny_constraints
from sage.v2.semantics import execute, event_taint, is_safe


def audit(case, raw, original):
    guards = parse_candidate(case, raw)
    sc = build_scenario(case['spec'])
    assert is_safe(sc.initial_state, sc.policy)
    measured = assess_case(case, guards)
    for key in ('dangerous_probes', 'benign_probes', 'missed', 'blocked'):
        assert measured[key] == original[key], (case['id'], key)
    # Monotone union transitions: this closure overapproximates every state
    # reachable under any guard, including states beyond policy violations.
    upper = sc.initial_state
    while True:
        before = upper
        for action in sc.model.actions:
            upper = execute(upper, action)
        if upper == before:
            break
    assert all(execute(upper, action) == upper for action in sc.model.actions)
    gaps = certify_action_coverage(sc.model, sc.policy, guards).gaps
    details = [{'action': g.action.canonical(), 'missing': sorted(g.missing_labels),
                'possibly_reachable_missing': sorted(g.missing_labels & event_taint(upper, g.action))} for g in gaps]
    safe = all(not g['possibly_reachable_missing'] for g in details)
    actions = dict(zip((a['id'] for a in case['actions']), sc.model.actions))
    witness = None
    for mismatch in measured['mismatches']:
        if not mismatch['expected_deny'] or mismatch['actual_deny']:
            continue
        prefix = ([f'import_{label}' for label in mismatch['seed']] if case['family'] == 'support_finance'
                  else [case['import_actions'][label] for label in mismatch['seed']]) + list(mismatch['path'])
        state = sc.initial_state
        admitted = True
        for identity in prefix:
            action = actions[identity]
            if deny_constraints(guards, state, action):
                admitted = False
                break
            state = execute(state, action)
            assert is_safe(state, sc.policy)
        target = actions[mismatch['action']]
        if admitted and not deny_constraints(guards, state, target) and not is_safe(execute(state, target), sc.policy):
            witness = {'prefix': prefix, 'target': mismatch['action'], 'seed': mismatch['seed']}
            break
    assert not (safe and witness), case['id']
    status = 'PASS' if safe else ('FAIL' if witness else 'UNKNOWN')
    return {'workflow': case['id'], 'count': case['dispatch_count'], 'original_status': original['verification_status'],
            'audited_status': status, 'candidate_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'coverage_gaps': details, 'replayed_unsafe_witness': witness,
            'fixed_probe_counts_unchanged': True,
            **{k: measured[k] for k in ('dangerous_probes','benign_probes','missed','blocked')}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--records-root', type=Path, default=Path('artifacts/fse2027/authoring72/raw'))
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    datasets = {}
    mimo = json.loads((args.records_root/'records/mimo25_composition_final_originals_20260919/selected_results.json').read_text('utf-8'))['records']
    datasets['mimo'] = [audit(build_case(r['family'],r['count']),r['initial_raw_content'],r['initial']) for r in mimo]
    gpt = json.loads((args.records_root/'records/ikuncode_gpt55_authoring_72_final_20260919/results.json').read_text('utf-8'))['records']
    rows = []
    for r in gpt:
        if r['layer'] != 'composition': continue
        source_relative = r['source'].replace('\\', '/')
        assert source_relative.startswith('output/'), source_relative
        source = json.loads((args.records_root/'records'/source_relative[len('output/'):]).read_text('utf-8'))['records']
        record = next(v for v in source if v['workflow'] == r['workflow'])
        rows.append(audit(build_case(record['family'],record['count']),record['raw_content'],r['initial']))
    datasets['gpt55'] = rows
    summary = {model: dict(Counter(r['audited_status'] for r in rows)) for model,rows in datasets.items()}
    payload = {'method':'unguarded monotone label closure + per-witness guarded replay',
               'scope':'36 frozen composition drafts per author; base results unchanged',
               'summary':summary, 'records': datasets}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f: json.dump(payload,f,indent=2)
    print(json.dumps(summary))

if __name__ == '__main__': main()
