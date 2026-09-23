"""Offline AgentSpec documented-extension feasibility test; NOT an LLM evaluation."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import itertools
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / 'external/AgentSpec'
COMMIT = 'e6fa3902e2cfb9681f454b355691b771f70543f8'
JAVA = Path('D:/SpringBoot/jdk-17.0.8/bin/java.exe')


def prepare(out):
    archive = subprocess.check_output(['git', '-C', str(UPSTREAM), 'archive', '--format=zip', COMMIT, 'src', 'README.md'])
    runtime = out / 'runtime'
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        z.extractall(runtime)
    grammar = runtime / 'src/spec_lang/AgentSpec.g4'
    original = grammar.read_text(encoding='utf-8')
    assert 'sage_policy_violation' not in original
    # Exactly the extension procedure documented in the upstream README.
    edited = []
    for line in original.splitlines():
        if line.startswith('PREDICATE:'):
            line = line.replace(';', " | 'pilot_candidate' | 'pilot_completion' ;", 1)
        edited.append(line)
    grammar.write_text('\n'.join(edited) + '\n', encoding='utf-8')
    subprocess.run([str(JAVA), '-jar', str(grammar.parent / 'antlr-4.13.2-complete.jar'),
                    '-Dlanguage=Python3', grammar.name], cwd=grammar.parent, check=True, capture_output=True)
    for p in (ROOT, runtime / 'src'):
        sys.path.insert(0, str(p))
    return runtime


def rule_text(predicate):
    return f'rule @{predicate}_rule\ntrigger\n send\ncheck\n {predicate}\nenforce\n stop\nend\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runtime = prepare(args.output)
    from agent import Action
    from enforcement import EnforceResult
    from interpreter import RuleInterpreter
    from rule import Rule
    from state import RuleState
    from rules.manual.table import predicate_table
    from sage.v2.model import Location, ToolModel, make_action, make_policy, make_state
    from sage.v2.counterexample import shortest_counterexample, counterexample_to_llm_json
    from sage.v2.semantics import event_taint, execute, is_safe, deny_star
    from sage.v2.synthesis import direct_sage
    from sage.v2.guards import deny_constraints

    secret, public = Location.slot('resource', 'sensitive'), Location.slot('resource', 'public')
    inside, outside = Location.slot('sink', 'internal'), Location.slot('sink', 'external')
    initial = make_state({secret: ['SECRET']})
    actions = tuple(make_action('operator', 'send', {'resource': resource, 'destination': dest, 'mode': mode},
                               reads=[secret if resource == 'sensitive' else public],
                               writes=[outside if dest == 'external' else inside])
                    for resource, dest, mode in itertools.product(['sensitive', 'public'], ['internal', 'external'], ['single', 'batch']))
    model = ToolModel(frozenset({'operator'}), frozenset({'send'}), frozenset({secret, public, inside, outside}),
                      frozenset({'SECRET'}), actions)
    policy = make_policy({outside: ['SECRET']})
    direct = direct_sage(model, policy)
    # Emit ordinary Python for the documented extension interface, not a call
    # back to SAGE's decision function. Raw params and the same trusted labels
    # are supplied to both the candidate and completed arms.
    clauses = [{'agent': c.agent, 'tool': c.tool,
                'patterns': [dict(p) for p in c.param_filter.exact_patterns],
                'labels': sorted(c.forbidden_labels)} for c in direct]
    completion_source = 'import json\nCLAUSES = ' + repr(clauses) + '''
def pilot_completion(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and params in c['patterns']
               and bool(set(user_input['trusted_event_labels']) & set(c['labels']))
               for c in CLAUSES)
'''
    ns = {}
    exec(completion_source, ns)
    predicate_table['pilot_completion'] = ns['pilot_completion']
    (args.output / 'completion.py').write_text(completion_source, encoding='utf-8')
    (args.output / 'completion.rule').write_text(rule_text('pilot_completion'), encoding='utf-8')
    completion_rule = Rule.from_text(rule_text('pilot_completion'))
    candidate_rule = Rule.from_text(rule_text('pilot_candidate'))

    class NativeGuard:
        """SAGE checker callback executes the real AgentSpec predicate/runtime."""
        def __init__(self, rules):
            self.rules = rules
            self.invocations = 0
        def trigger(self, state, action):
            self.invocations += 1
            call = Action(name=action.tool, input=json.dumps(action.params, sort_keys=True), action=None)
            facts = {'agent': action.agent, 'tool': action.tool, 'trusted_event_labels': sorted(event_taint(state, action))}
            with contextlib.redirect_stdout(io.StringIO()):
                for rule in self.rules:
                    if not rule.triggered(call.name, call.input):
                        continue
                    rule_state = RuleState(action=call, agent=None, intermediate_steps=[], user_input=facts)
                    result, _ = RuleInterpreter(rule, rule_state).verify_and_enforce(call)
                    if result == EnforceResult.STOP:
                        return True
            return False

    # All safe reachable states are included in a compiler conformance check.
    states = {initial}
    queue = [initial]
    while queue:
        state = queue.pop()
        for action in actions:
            post = execute(state, action)
            if is_safe(post, policy) and post not in states:
                states.add(post)
                queue.append(post)
    compiled = NativeGuard([completion_rule])
    for state, action in itertools.product(states, actions):
        assert compiled.trigger(state, action) == deny_constraints(direct, state, action)

    candidates = {
        'missing_batch_branch': "p['destination'] == 'external' and p['mode'] == 'single' and secret",
        'overbroad_destination': 'secret',
        'correct_parameter_rule': "p['destination'] == 'external' and secret",
    }
    rows = []
    for name, expression in candidates.items():
        source = 'import json\ndef pilot_candidate(user_input, tool_input, intermediate_steps):\n'
        source += '    p = json.loads(tool_input)\n    secret = "SECRET" in user_input["trusted_event_labels"]\n'
        source += '    return ' + expression + '\n'
        ns = {}
        exec(source, ns)
        predicate_table['pilot_candidate'] = ns['pilot_candidate']
        (args.output / (name + '.py')).write_text(source, encoding='utf-8')
        (args.output / (name + '.rule')).write_text(rule_text('pilot_candidate'), encoding='utf-8')
        for arm, rules in [('candidate', [candidate_rule]), ('candidate_plus_sage', [candidate_rule, completion_rule])]:
            guard = NativeGuard(rules)
            witness = shortest_counterexample(model, policy, [guard], initial, max_states=100)
            probes = []
            for action in actions:
                dangerous = action.params['resource'] == 'sensitive' and action.params['destination'] == 'external'
                assert dangerous == deny_star(initial, action, policy)
                probes.append({'params': action.params, 'dangerous': dangerous, 'denied': guard.trigger(initial, action)})
            d = [p for p in probes if p['dangerous']]
            b = [p for p in probes if not p['dangerous']]
            rows.append({'candidate': name, 'arm': arm, 'status': 'FAIL' if witness else 'PASS',
                         'dangerous_denied': sum(p['denied'] for p in d), 'dangerous': len(d),
                         'benign_denied': sum(p['denied'] for p in b), 'benign': len(b),
                         'runtime_invocations': guard.invocations, 'probes': probes,
                         'counterexample': counterexample_to_llm_json(witness) if witness else None})
    expected = [('FAIL', 1, 0), ('PASS', 2, 0), ('PASS', 2, 2), ('PASS', 2, 2), ('PASS', 2, 0), ('PASS', 2, 0)]
    assert [(r['status'], r['dangerous_denied'], r['benign_denied']) for r in rows] == expected
    result = {'purpose': 'manual adapter feasibility only; no LLM outputs or comparative performance claim',
              'commit': COMMIT, 'extension': 'README documented grammar registration and Python predicates',
              'observation': 'same host-supplied trusted event labels and unmodified call params for both arms',
              'verification_scope': 'finite model; deterministic stateless predicates; history-dependent predicates excluded',
              'safe_states': len(states), 'compiler_conformance_checks': len(states) * len(actions),
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'results': rows}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    deps = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    (args.output / 'requirements-frozen.txt').write_text(deps, encoding='utf-8')
    lines = ['# AgentSpec documented-extension feasibility pilot', '',
             'Manual fixtures; not LLM evaluation and not manuscript performance evidence.', '',
             '| Case | Arm | Verification | Dangerous denied | Benign denied |',
             '|---|---|---|---:|---:|']
    for row in rows:
        lines.append(f"| {row['candidate']} | {row['arm']} | {row['status']} | {row['dangerous_denied']}/{row['dangerous']} | {row['benign_denied']}/{row['benign']} |")
    lines += ['', f"Compiler equivalence checked on {len(states)*len(actions)} safe-state/action combinations.",
              'The real RuleInterpreter and STOP enforcement ran. Full LangChain agent-loop / physical tool dispatch is not tested here.',
              'This is a supported custom-predicate integration; the benchmark policies are supplied by this experiment, not the AgentSpec authors.']
    (args.output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
