import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    agent = user_input.get('agent', '')
    tool = user_input.get('tool', '')
    trusted_labels = user_input.get('trusted_event_labels', [])
    trusted_set = set(trusted_labels)
    destination = None
    if agent == 'refunds' and tool == 'notify':
        destination = 'audit'
    elif agent == 'refunds' and tool == 'issue_receipt':
        destination = 'merchant'
    elif agent == 'merchant_relations' and tool == 'update':
        destination = 'merchant'
    elif agent == 'customer_care' and tool == 'update':
        destination = 'internal'
    else:
        destination = 'case'
    forbidden_map = {
        'audit': ['TOKEN'],
        'merchant': ['PII', 'TOKEN']
    }
    if destination in forbidden_map:
        forbidden_set = set(forbidden_map[destination])
        if trusted_set.intersection(forbidden_set):
            return True
    return False