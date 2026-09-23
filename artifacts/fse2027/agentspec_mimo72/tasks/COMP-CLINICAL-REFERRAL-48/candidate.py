import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    agent = user_input.get('agent')
    trusted_labels = user_input.get('trusted_event_labels')
    tool_name = user_input.get('tool')

    if tool_name != 'route_referral':
        return False

    destination = params.get('destination')
    record = params.get('record')

    dest_slot = None
    if agent == 'care':
        if destination == 'local':
            dest_slot = 'slot:hospital'
        elif destination == 'partner':
            dest_slot = 'slot:scheduler'
        elif destination == 'release':
            dest_slot = 'slot:public'
    elif agent == 'research':
        if destination == 'local':
            dest_slot = 'slot:hospital'
        elif destination == 'partner':
            dest_slot = 'slot:research'
        elif destination == 'release':
            dest_slot = 'slot:lab'

    rec_slot = None
    if record == 'audit':
        rec_slot = 'slot:audit'
    elif record == 'partner':
        rec_slot = 'slot:partner'
    elif record == 'public':
        rec_slot = 'slot:public'

    policy = {
        'slot:audit': ['DIAGNOSIS', 'AUTH'],
        'slot:lab': ['PATIENT', 'AUTH'],
        'slot:public': ['PATIENT', 'DIAGNOSIS', 'AUTH'],
        'slot:research': ['PATIENT', 'UNVERIFIED'],
        'slot:scheduler': ['DIAGNOSIS', 'AUTH']
    }

    if dest_slot in policy:
        allowed = policy[dest_slot]
        if not all(label in allowed for label in trusted_labels):
            return True

    if rec_slot in policy:
        allowed = policy[rec_slot]
        if not all(label in allowed for label in trusted_labels):
            return True

    return False
