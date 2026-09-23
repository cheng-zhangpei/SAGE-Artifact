import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path


ARMS = ('candidate', 'candidate_plus_sage', 'direct_sage')


def group_name(record):
    if record['layer'] == 'base':
        return 'Base (W01--W36)'
    count = record['id'].rsplit('-', 1)[-1]
    return f'Composition-{count}'


def aggregate(records, arm):
    metrics = [record['metrics'][arm] for record in records]
    dangerous = sum(m['dangerous'] for m in metrics)
    benign = sum(m['benign'] for m in metrics)
    missed = sum(m['missed'] for m in metrics)
    blocked = sum(m['blocked'] for m in metrics)
    status = Counter(m['status'] for m in metrics)
    return {
        'pass': status['PASS'], 'fail': status['FAIL'], 'unknown': status['UNKNOWN'],
        'der': None if not dangerous else 100 * (dangerous - missed) / dangerous,
        'bbr': None if not benign else 100 * blocked / benign,
        'unknown_probes': sum(m.get('unknown_probes', 0) for m in metrics),
    }


def clauses(task_dir):
    tree = ast.parse((task_dir / 'completion.py').read_text(encoding='utf-8'))
    value = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == 'CLAUSES' for target in node.targets))
    data = ast.literal_eval(value)
    return len(data), sum(len(item['patterns']) for item in data)


def percent(value):
    return '--' if value is None else f'{value:.2f}%'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = []
    task_dirs = sorted((args.output / 'tasks').iterdir())
    for task_dir in task_dirs:
        if not task_dir.is_dir():
            continue
        record = json.loads((task_dir / 'evaluation.json').read_text(encoding='utf-8'))
        if 'error' in record:
            raise ValueError(f'Unresolved evaluator error in {task_dir.name}: {record}')
        records.append(record)
    if len(records) != 72:
        raise ValueError(f'Expected 72 evaluations, found {len(records)}')

    by_group = defaultdict(list)
    for record in records:
        by_group[group_name(record)].append(record)
    order = ['Base (W01--W36)', *[f'Composition-{n:02d}' for n in (8, 16, 24, 32, 40, 48)]]
    clause_counts = [clauses(args.output / 'tasks' / record['id']) for record in records]
    runtime_invalid = [record for record in records if record['metrics']['candidate_plus_sage']['status'] == 'UNKNOWN']
    inconclusive = [record for record in records
                    if record['metrics']['candidate']['status'] == 'UNKNOWN'
                    and record['metrics']['candidate_plus_sage']['status'] == 'PASS']
    amendments = sorted(str(path.relative_to(args.output)) for path in args.output.glob('tasks/*/generation_amendment.json'))
    normalizations = sorted(str(path.relative_to(args.output)) for path in args.output.glob('tasks/*/candidate_normalization.json'))
    summary = {
        'tasks': len(records),
        'overall': {arm: aggregate(records, arm) for arm in ARMS},
        'by_complexity': {name: {arm: aggregate(by_group[name], arm) for arm in ARMS} for name in order},
        'completion': {
            'clauses_min': min(x[0] for x in clause_counts),
            'clauses_max': max(x[0] for x in clause_counts),
            'clauses_median_upper': sorted(x[0] for x in clause_counts)[len(clause_counts)//2],
            'patterns_min': min(x[1] for x in clause_counts),
            'patterns_max': max(x[1] for x in clause_counts),
            'patterns_median_upper': sorted(x[1] for x in clause_counts)[len(clause_counts)//2],
        },
        'runtime_invalid': [record['id'] for record in runtime_invalid],
        'inconclusive_without_fixed_witness': [record['id'] for record in inconclusive],
        'generation_amendments': amendments,
        'source_normalizations': normalizations,
    }
    (args.output / 'final_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    lines = [
        '# AgentSpec + SAGE full-72 assessment', '',
        'Status: complete. All 72 frozen tasks were executed through the upstream AgentSpec '
        '`RuleInterpreter` and STOP enforcement. The predicates and policies are study-authored; '
        'they are not rules supplied by the AgentSpec authors.', '',
        '## Overall result', '',
        '| Arm | PASS | FAIL | UNKNOWN | Probe DER | Probe BBR |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for arm in ARMS:
        value = aggregate(records, arm)
        lines.append(f"| {arm} | {value['pass']} | {value['fail']} | {value['unknown']} | {percent(value['der'])} | {percent(value['bbr'])} |")
    lines += ['',
        'DER and BBR use evaluable fixed probes; probes affected by a candidate runtime error are '
        'reported as unknown and excluded from those denominators. PASS/FAIL/UNKNOWN therefore '
        'remains the primary candidate-level outcome.', '',
        '## Complexity breakdown for the MiMo-authored AgentSpec predicate', '',
        '| Layer | Tasks | PASS / FAIL / UNKNOWN | Probe DER | Probe BBR | Unknown probes |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for name in order:
        value = aggregate(by_group[name], 'candidate')
        lines.append(f"| {name} | {len(by_group[name])} | {value['pass']} / {value['fail']} / {value['unknown']} | {percent(value['der'])} | {percent(value['bbr'])} | {value['unknown_probes']} |")
    lines += ['',
        'The base layer is 25/9/2. The composition layer is 1/28/7 across six correlated '
        'business-family clusters and six nested complexity levels. The composition rows are '
        'not independent domains and do not form a monotone statistical dose-response curve.', '',
        '## What SAGE changes', '',
        '- Additive completion certifies all 67 executable predicates in one deterministic pass '
        'and witnesses no remaining dangerous fixed probe. It does not make the five runtime-invalid '
        'predicates deployable.',
        '- Additive completion preserves candidate denials, so aggregate BBR remains 30.79%. This is '
        'an expected limitation rather than a repair failure.',
        '- DirectSAGE ignores the candidate and compiles from the separately confirmed model/policy. '
        'It is 72/72 PASS with DER 100% and BBR 0% on the model-relative finite domain.',
        f"- The compiled completion contains {min(x[0] for x in clause_counts)}--{max(x[0] for x in clause_counts)} normalized clauses "
        f"and {min(x[1] for x in clause_counts)}--{max(x[1] for x in clause_counts)} exact action patterns per task (medians: "
        f"{sorted(x[0] for x in clause_counts)[len(clause_counts)//2]} clauses and "
        f"{sorted(x[1] for x in clause_counts)[len(clause_counts)//2]} patterns). It uses no additional LLM repair round.", '',
        '## UNKNOWN outcomes', '',
        f"Five predicates are runtime-invalid under the actual AgentSpec inputs: {', '.join(record['id'] for record in runtime_invalid)}. "
        'They remain UNKNOWN in the additive arm.',
        f"Four other predicates lack complete finite-domain coverage but have no fixed executable witness: {', '.join(record['id'] for record in inconclusive)}. "
        'They are UNKNOWN as candidates; deterministic completion certifies the combined guard.', '',
        '## Audit notes', '',
        '- The task set was fixed as all 36 base workflows plus all 6 x 6 composition tasks; no '
        'selection used model outcomes.',
        '- Twenty-four prompt-identical pilot responses were reused after SHA256 checks; the '
        'remaining 48 were generated once for this extension.',
        f"- Generation amendments retained: {len(amendments)} ({', '.join(amendments) if amendments else 'none'}).",
        f"- Deterministic source normalizations retained: {len(normalizations)} ({', '.join(normalizations) if normalizations else 'none'}).",
        '- Evaluator compatibility revisions and pre-final evaluations are retained alongside each '
        'affected task. Final results were recomputed for all 72 responses with one evaluator version.',
        '- The regression suite has 11 tests covering the upstream runtime, finite-suite selection, '
        'parameter sensitivity, runtime-invalid candidates, supported pure-Python forms, and rejection '
        'of external effects.', '',
        '## Inclusion recommendation', '',
        'Include this as an independent-runtime augmentation study. Phrase the baseline as '
        '“MiMo-authored AgentSpec predicates,” not “AgentSpec accuracy.” The experiment supports '
        'runtime portability of SAGE verification/completion and the engineering value of checking '
        'custom predicates. It does not estimate production guard failure rates, validate the confirmed '
        'models, or establish that AgentSpec authors supplied defective policies.', '',
        'Keep CaMeL outside this quantitative table. Its privileged-program interpreter, value '
        'capabilities, suite-specific policy engines, and AgentDojo objective change the treatment and '
        'outcome. See `CAMEL_BASELINE_ASSESSMENT.md`.',
    ]
    (args.output / 'FINAL_ASSESSMENT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:35]))


if __name__ == '__main__':
    main()
