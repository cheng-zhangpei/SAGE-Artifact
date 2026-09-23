import json
CLAUSES = [{'agent': 'exporter', 'tool': 'export', 'patterns': [{'region': 'eu'}], 'labels': ['US_SUBJECT']}, {'agent': 'exporter', 'tool': 'export', 'patterns': [{'region': 'us'}], 'labels': ['EU_SUBJECT']}, {'agent': 'exporter', 'tool': 'export', 'patterns': [{'region': 'demo'}], 'labels': ['EU_SUBJECT', 'US_SUBJECT']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
