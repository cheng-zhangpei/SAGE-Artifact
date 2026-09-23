import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool_name = user_input.get('tool', '')
    trusted_labels = user_input.get('trusted_event_labels', [])
    if tool_name == 'release':
        route = params.get('route', '')
        if route in ['web', 'mail'] and 'EMBARGO' in trusted_labels:
            return True
    return False