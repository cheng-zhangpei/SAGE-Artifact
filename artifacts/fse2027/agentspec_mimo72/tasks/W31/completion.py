import json
CLAUSES = [{'agent': 'mailer', 'tool': 'send', 'patterns': [{'scope': 'all', 'to': 'a'}, {'scope': 'own', 'to': 'a'}], 'labels': ['CLIENT_B']}, {'agent': 'mailer', 'tool': 'send', 'patterns': [{'scope': 'all', 'to': 'b'}, {'scope': 'own', 'to': 'b'}], 'labels': ['CLIENT_A']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
