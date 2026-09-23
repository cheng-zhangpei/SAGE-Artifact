import json
def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input.get('tool')
    trusted_labels = set(user_input.get('trusted_event_labels', []))
    params = json.loads(tool_input) if tool_input else {}
    if tool_name == 'send':
        target = params.get('target', '')
        if target == 'research':
            return 'POSITION' in trusted_labels
        elif target == 'sales':
            return 'MNPI' in trusted_labels
        else:
            return False
    else:
        return False