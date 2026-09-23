import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    parsed_tool_input = json.loads(tool_input)
    tool = user_input.get('tool', None)
    if tool == 'send':
        target = parsed_tool_input.get('target', None)
        labels = user_input.get('trusted_event_labels', set())
        if target == 'notice':
            if 'PII' in labels or 'DETECTION_RULE' in labels:
                return True
            else:
                return False
        elif target == 'player':
            if 'DETECTION_RULE' in labels:
                return True
            else:
                return False
        elif target == 'security':
            return False
        else:
            return False
    else:
        return False