import json
CLAUSES = [{'agent': 'coordinator', 'tool': 'deliver', 'patterns': [{'email_copy': False, 'target': 'counsel'}], 'labels': ['TOKEN']}, {'agent': 'coordinator', 'tool': 'deliver', 'patterns': [{'email_copy': True, 'target': 'room'}], 'labels': ['PII', 'TOKEN']}, {'agent': 'coordinator', 'tool': 'deliver', 'patterns': [{'email_copy': False, 'target': 'investors'}], 'labels': ['PII', 'TOKEN', 'VALUATION']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
