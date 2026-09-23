import json
CLAUSES = [{'agent': 'teacher', 'tool': 'publish', 'patterns': [{'source': 'timetable', 'target': 'class_board'}, {'target': 'class_board'}], 'labels': ['GRADE', 'PII']}, {'agent': 'teacher', 'tool': 'publish', 'patterns': [{'target': 'identity_queue'}], 'labels': ['GRADE']}]
def pilot_completion(user_input, tool_input, intermediate_steps):
    p = json.loads(tool_input)
    return any(user_input['agent'] == c['agent'] and user_input['tool'] == c['tool']
               and p in c['patterns'] and not set(user_input['trusted_event_labels']).isdisjoint(c['labels'])
               for c in CLAUSES)
