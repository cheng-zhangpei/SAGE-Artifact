import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool_name = user_input.get('tool')
    trusted_labels = user_input.get('trusted_event_labels', set())
    if tool_name == 'collect':
        return False
    elif tool_name == 'route':
        destination = params.get('destination')
        archive = params.get('archive')
        if destination == 'customer' and 'PII' in trusted_labels:
            return True
        if archive == 'outsourced' and 'RISK' in trusted_labels:
            return True
        return False
    else:
        return False