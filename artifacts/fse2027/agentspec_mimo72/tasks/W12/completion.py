import json
CLAUSES = [{'agent': 'notifier', 'tool': 'announce', 'patterns': [{'attachments': False, 'target': 'status'}, {'attachments': True, 'target': 'status'}], 'labels': ['CREDENTIAL', 'PII']}, {'agent': 'notifier', 'tool': 'announce', 'patterns': [{'attachments': True, 'target': 'coordinator'}], 'labels': ['CREDENTIAL']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
