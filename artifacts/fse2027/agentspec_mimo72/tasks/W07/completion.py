import json
CLAUSES = [{'agent': 'merchant_relations', 'tool': 'update', 'patterns': [{'record': 'current'}], 'labels': ['PII', 'TOKEN']}, {'agent': 'refunds', 'tool': 'notify', 'patterns': [{'target': 'audit'}], 'labels': ['TOKEN']}, {'agent': 'refunds', 'tool': 'issue_receipt', 'patterns': [{'target': 'merchant'}], 'labels': ['PII', 'TOKEN']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
