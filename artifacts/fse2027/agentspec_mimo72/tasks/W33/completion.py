import json
CLAUSES = [{'agent': 'quality', 'tool': 'export', 'patterns': [{'join': False, 'target': 'text_vendor'}, {'join': True, 'target': 'text_vendor'}], 'labels': ['BIOMETRIC']}, {'agent': 'quality', 'tool': 'export', 'patterns': [{'join': False, 'target': 'acoustic'}, {'join': True, 'target': 'acoustic'}], 'labels': ['PII']}, {'agent': 'quality', 'tool': 'export', 'patterns': [{'join': True, 'target': 'both'}], 'labels': ['BIOMETRIC', 'PII']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
