import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool = user_input.get('tool')
    labels = user_input.get('trusted_event_labels', [])

    if tool == 'assemble':
        return False
    elif tool == 'export':
        target = params.get('target')
        cc = params.get('cc')

        if target == 'analytics' and 'PII' in labels:
            return True
        if target == 'public' and ('PII' in labels or 'SALARY' in labels):
            return True
        if cc and cc != 'none':
            if cc == 'analytics' and 'PII' in labels:
                return True
            if cc == 'public' and ('PII' in labels or 'SALARY' in labels):
                return True
        return False
    else:
        return False