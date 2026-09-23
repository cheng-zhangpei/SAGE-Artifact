import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input['tool']
    labels = user_input['trusted_event_labels']
    params = json.loads(tool_input)

    if tool_name == 'attach':
        return False
    elif tool_name == 'deliver':
        target = params.get('target')
        mirror_store = params.get('mirror_store')
        if target == 'signing':
            return False
        elif target == 'review':
            if not mirror_store:
                if 'PRIVATE_KEY' in labels:
                    return True
                else:
                    return False
            else:
                if 'PRIVATE_KEY' in labels or 'ROADMAP' in labels:
                    return True
                else:
                    return False
        elif target == 'store':
            if 'PRIVATE_KEY' in labels or 'ROADMAP' in labels:
                return True
            else:
                return False
        else:
            return False
    else:
        return False
