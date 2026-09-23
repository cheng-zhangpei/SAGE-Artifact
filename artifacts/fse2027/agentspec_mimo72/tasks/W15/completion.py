import json
CLAUSES = [{'agent': 'bank', 'tool': 'route', 'patterns': [{'archive': 'outsourced', 'destination': 'regulator'}], 'labels': ['PII']}, {'agent': 'bank', 'tool': 'route', 'patterns': [{'archive': 'internal', 'destination': 'customer'}], 'labels': ['RISK']}, {'agent': 'bank', 'tool': 'route', 'patterns': [{'archive': 'outsourced', 'destination': 'customer'}], 'labels': ['PII', 'RISK']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
