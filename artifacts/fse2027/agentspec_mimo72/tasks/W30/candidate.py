import json
def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool = user_input.get('tool', '')
    data = json.loads(tool_input)
    source = data.get('source', '')
    target = data.get('target', '')
    labels = user_input.get('trusted_event_labels', {})
    if tool == 'upload' and target == 'public':
        if source == 'formatted' or source == 'packet':
            if 'PII' in labels:
                return True
        elif source == 'status':
            return False
    if tool == 'upload' and target == 'approval':
        return False
    if tool == 'collect' or tool == 'format_public':
        return False
    return False