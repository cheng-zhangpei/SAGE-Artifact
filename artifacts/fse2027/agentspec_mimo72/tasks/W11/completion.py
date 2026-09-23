import json
CLAUSES = [{'agent': 'support', 'tool': 'respond', 'patterns': [{'fallback': False, 'tenant': 'a'}, {'fallback': True, 'tenant': 'a'}], 'labels': ['TENANT_B']}, {'agent': 'support', 'tool': 'respond', 'patterns': [{'fallback': False, 'tenant': 'b'}], 'labels': ['TENANT_A']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
