import json
CLAUSES = [{'agent': 'coordinator', 'tool': 'send', 'patterns': [{'target': 'delivery'}], 'labels': ['HARDSHIP']}, {'agent': 'campaign', 'tool': 'publish', 'patterns': [{'include_case': False}, {'include_case': True}], 'labels': ['HARDSHIP', 'PII']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
