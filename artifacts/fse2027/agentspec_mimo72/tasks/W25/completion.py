import json
CLAUSES = [{'agent': 'storage', 'tool': 'backup', 'patterns': [{'manifest': False, 'route': 'vendor'}, {'manifest': True, 'route': 'primary'}], 'labels': ['PII']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
