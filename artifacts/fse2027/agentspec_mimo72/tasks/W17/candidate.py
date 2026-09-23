import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    trusted_labels = user_input.get('trusted_event_labels', [])
    tool = user_input.get('tool')

    if tool == 'publish':
        target = params.get('target', None)
        mirror = params.get('mirror', None)
        if target == 'tracking' or mirror == 'tracking':
            if 'ADDRESS' in trusted_labels:
                return True

    return False