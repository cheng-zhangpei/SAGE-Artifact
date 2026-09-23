import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool_name = user_input.get('tool')
    trusted_labels = set(user_input.get('trusted_event_labels'))

    if tool_name == 'collect':
        return False
    elif tool_name == 'simulate':
        return False
    elif tool_name == 'apply':
        target = params.get('target')
        if target == 'control':
            return bool(trusted_labels.intersection({'UNVERIFIED'}))
        elif target == 'display':
            return bool(trusted_labels.intersection({'CONFIDENTIAL'}))
        elif target == 'internal':
            return False
        else:
            return False
    else:
        return False