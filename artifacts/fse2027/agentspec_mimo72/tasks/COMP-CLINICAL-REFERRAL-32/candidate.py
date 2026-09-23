import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input['agent']
    tool = user_input['tool']
    trusted_labels = set(user_input['trusted_event_labels'])

    # Policy: slot -> allowed categories
    policy = {
        'slot:audit': ['DIAGNOSIS', 'AUTH'],
        'slot:lab': ['PATIENT', 'AUTH'],
        'slot:public': ['PATIENT', 'DIAGNOSIS', 'AUTH'],
        'slot:research': ['PATIENT', 'UNVERIFIED'],
        'slot:scheduler': ['DIAGNOSIS', 'AUTH']
    }

    # Only route_referral may write to restricted slots; others are unrestricted
    if tool != 'route_referral':
        return False

    params = json.loads(tool_input)
    dest_param = params.get('destination')
    record_param = params.get('record')

    # Determine main destination slot based on agent and destination
    dest_slot = None
    if agent == 'care':
        if dest_param == 'local':
            dest_slot = 'slot:hospital'
        elif dest_param == 'partner':
            dest_slot = 'slot:scheduler'
        elif dest_param == 'release':
            dest_slot = 'slot:public'
        else:
            # Unknown destination for care agent
            return True
    elif agent == 'research':
        if dest_param == 'local':
            dest_slot = 'slot:hospital'
        elif dest_param == 'partner':
            dest_slot = 'slot:research'
        elif dest_param == 'release':
            dest_slot = 'slot:lab'
        else:
            # Unknown destination for research agent
            return True
    else:
        # Unknown agent using route_referral
        return True

    # Determine record destination slot
    record_slot = None
    if record_param == 'audit':
        record_slot = 'slot:audit'
    elif record_param == 'public':
        record_slot = 'slot:public'
    elif record_param == 'partner':
        # Not in policy, so no restriction
        record_slot = None
    elif record_param == 'none':
        record_slot = None
    else:
        # Unknown record parameter
        return True

    # Check main destination
    if dest_slot in policy:
        allowed = set(policy[dest_slot])
        if not trusted_labels.issubset(allowed):
            return True

    # Check record destination
    if record_slot in policy:
        allowed = set(policy[record_slot])
        if not trusted_labels.issubset(allowed):
            return True

    return False