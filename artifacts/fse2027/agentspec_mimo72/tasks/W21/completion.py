import json
CLAUSES = [{'agent': 'dispatcher', 'tool': 'send', 'patterns': [{'target': 'rider'}], 'labels': ['HEALTH']}, {'agent': 'dispatcher', 'tool': 'send', 'patterns': [{'source': 'menu', 'target': 'review'}, {'target': 'review'}], 'labels': ['ADDRESS', 'HEALTH']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
