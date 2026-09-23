import json
CLAUSES = [{'agent': 'release', 'tool': 'deliver', 'patterns': [{'mirror_store': False, 'target': 'review'}], 'labels': ['PRIVATE_KEY']}, {'agent': 'release', 'tool': 'deliver', 'patterns': [{'mirror_store': False, 'target': 'store'}, {'mirror_store': True, 'target': 'review'}], 'labels': ['PRIVATE_KEY', 'ROADMAP']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
