import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool_input
    params = json.loads(tool_input)

    # Get agent and tool from user_input
    agent = user_input.get('agent')
    tool = user_input.get('tool')
    trusted_labels = set(user_input.get('trusted_event_labels', []))

    # Define policy as a constant from the input
    policy_dict = {
        'slot:audit': ['DIAGNOSIS', 'AUTH'],
        'slot:lab': ['PATIENT', 'AUTH'],
        'slot:public': ['PATIENT', 'DIAGNOSIS', 'AUTH'],
        'slot:research': ['PATIENT', 'UNVERIFIED'],
        'slot:scheduler': ['DIAGNOSIS', 'AUTH']
    }

    # If tool is not route_referral, allow (no policy restrictions on internal slots)
    if tool != 'route_referral':
        return False

    # For route_referral, determine destination and record slots
    destination = params.get('destination')
    record = params.get('record')

    # Map destination to slot based on agent
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

    # Map record to slot
    rec_slot = None
    if record == 'audit':
        rec_slot = 'slot:audit'
    elif record == 'partner':
        rec_slot = 'slot:partner'
    elif record == 'public':
        rec_slot = 'slot:public'
    # record 'none' leaves rec_slot as None

    # Collect slots to check for write compliance
    slots_to_check = []
    if dest_slot is not None:
        slots_to_check.append(dest_slot)
    if rec_slot is not None:
        slots_to_check.append(rec_slot)

    # Check each slot against policy
    for slot in slots_to_check:
        if slot in policy_dict:
            allowed_categories = set(policy_dict[slot])
            if not trusted_labels.issubset(allowed_categories):
                return True  # Stop call if any violation

    # If all checks pass, allow the call
    return False