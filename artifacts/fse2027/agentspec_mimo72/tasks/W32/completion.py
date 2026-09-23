import json
CLAUSES = [{'agent': 'bot', 'tool': 'send_summary', 'patterns': [{'include_reproducer': False, 'target': 'issues'}, {'include_reproducer': True, 'target': 'issues'}, {'mirror': True, 'target': 'maintainer'}], 'labels': ['EXPLOIT']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
