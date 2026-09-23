import json
CLAUSES = [{'agent': 'portal', 'tool': 'upload', 'patterns': [{'source': 'formatted', 'target': 'public'}, {'source': 'packet', 'target': 'public'}, {'source': 'status', 'target': 'public'}], 'labels': ['PII']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
