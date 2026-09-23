import json
CLAUSES = [{'agent': 'operator', 'tool': 'backup', 'patterns': [{'remote': True}], 'labels': ['CREDENTIAL']}, {'agent': 'operator', 'tool': 'upload', 'patterns': [{'target': 'issue'}], 'labels': ['CREDENTIAL']}, {'agent': 'operator', 'tool': 'open_session', 'patterns': [{'target': 'vendor'}], 'labels': ['CREDENTIAL']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
