import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool = user_input.get('tool', '')
    trusted_labels = set(user_input.get('trusted_event_labels', []))

    if tool == 'collect':
        return False
    elif tool == 'send':
        target = params.get('target', '')
        allowed = {'candidate': {'INTERNAL_SCORE'}, 'jobs': {'PII', 'INTERNAL_SCORE'}, 'archive': {'PII', 'INTERNAL_SCORE'}}
        if target in allowed:
            allowed_set = allowed[target]
        else:
            allowed_set = {'PII', 'INTERNAL_SCORE'}
        if not trusted_labels.issubset(allowed_set):
            return True
        else:
            return False
    else:
        return False
