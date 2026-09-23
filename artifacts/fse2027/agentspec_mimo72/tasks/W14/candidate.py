import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool_name = user_input['tool']
    agent = user_input['agent']
    labels = user_input['trusted_event_labels']

    policy = {
        'courier': ['PHI'],
        'debug': ['PHI', 'POLICY_ID']
    }

    if tool_name == 'submit':
        target = params.get('target', '')
        if target in policy:
            forbidden = policy[target]
            if any(label in forbidden for label in labels):
                return True

    return False