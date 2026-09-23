import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    if user_input['tool'] == 'apply':
        params = json.loads(tool_input)
        target = params.get('target')
        labels = user_input.get('trusted_event_labels', [])
        if target == 'production' and 'UNVERIFIED' in labels:
            return True
    return False