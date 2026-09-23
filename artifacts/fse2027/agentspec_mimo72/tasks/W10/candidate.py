import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool = user_input.get('tool')
    labels = user_input.get('trusted_event_labels', [])

    if tool == 'prepare' or tool == 'calculate':
        return False
    elif tool == 'publish':
        target = params.get('target')
        if target == 'class_board':
            if 'PII' in labels or 'GRADE' in labels:
                return True
            else:
                return False
        elif target == 'identity_queue':
            if 'GRADE' in labels:
                return True
            else:
                return False
        elif target == 'student_portal':
            return False
        else:
            return False
    else:
        return False