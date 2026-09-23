import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input['tool']
    params = json.loads(tool_input)
    trusted_labels = user_input['trusted_event_labels']
    if tool_name == 'send' and params.get('target') == 'delivery':
        if 'PII' in trusted_labels:
            return True
    return False