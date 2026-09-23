import json
CLAUSES = [{'agent': 'operator', 'tool': 'apply', 'patterns': [{'target': 'control'}], 'labels': ['UNVERIFIED']}, {'agent': 'operator', 'tool': 'apply', 'patterns': [{'target': 'display'}], 'labels': ['CONFIDENTIAL']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
