import json
CLAUSES = [{'agent': 'sender', 'tool': 'submit', 'patterns': [{'receipt': 'verbose', 'target': 'insurer'}], 'labels': ['PHI', 'POLICY_ID']}, {'agent': 'sender', 'tool': 'submit', 'patterns': [{'receipt': 'normal', 'target': 'courier'}], 'labels': ['PHI']}, {'agent': 'sender', 'tool': 'receipt', 'patterns': [{'target': 'debug'}], 'labels': ['PHI', 'POLICY_ID']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
