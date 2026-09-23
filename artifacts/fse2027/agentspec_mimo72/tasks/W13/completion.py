import json
CLAUSES = [{'agent': 'coordinator', 'tool': 'send', 'patterns': [{'source': 'contact', 'target': 'candidate'}, {'source': 'packet', 'target': 'candidate'}], 'labels': ['INTERNAL_SCORE']}, {'agent': 'coordinator', 'tool': 'send', 'patterns': [{'source': 'packet', 'target': 'jobs'}], 'labels': ['INTERNAL_SCORE', 'PII']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
