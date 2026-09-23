import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    trusted_labels = user_input.get('trusted_event_labels', [])
    tool_name = user_input.get('tool')
    agent = user_input.get('agent')
    params = json.loads(tool_input) if tool_input else {}

    # Policy dictionary defining allowed categories for each slot
    policy = {
        'slot:audit': ['DIAGNOSIS', 'AUTH'],
        'slot:lab': ['PATIENT', 'AUTH'],
        'slot:public': ['PATIENT', 'DIAGNOSIS', 'AUTH'],
        'slot:research': ['PATIENT', 'UNVERIFIED'],
        'slot:scheduler': ['DIAGNOSIS', 'AUTH']
    }

    # For tools that don't write to policy-restricted slots, allow the call
    if tool_name not in ['route_referral']:
        return False

    # Handle route_referral tool
    destination_param = params.get('destination')
    record_param = params.get('record')

    # Map destination parameter to slot based on agent
    if agent == 'care':
        dest_map = {'local': 'slot:hospital', 'partner': 'slot:scheduler', 'release': 'slot:public'}
    elif agent == 'research':
        dest_map = {'local': 'slot:hospital', 'partner': 'slot:research', 'release': 'slot:lab'}
    else:
        # Unknown agent, disallow as a safety measure
        return True

    destination_slot = dest_map.get(destination_param)

    # Determine record slot
    record_slot = None
    if record_param == 'audit':
        record_slot = 'slot:audit'
    elif record_param == 'partner':
        if agent == 'care':
            record_slot = 'slot:scheduler'
        elif agent == 'research':
            record_slot = 'slot:research'
    elif record_param == 'public':
        record_slot = 'slot:public'
    elif record_param == 'none':
        record_slot = None

    # Collect slots to check for policy restrictions
    slots_to_check = []
    if destination_slot:
        slots_to_check.append(destination_slot)
    if record_slot:
        slots_to_check.append(record_slot)

    # Check if any trusted label is not allowed at any write slot
    for slot in slots_to_check:
        if slot in policy:
            allowed_categories = policy[slot]
            if any(label not in allowed_categories for label in trusted_labels):
                return True  # Stop the call due to policy violation

    return False  # No violations, allow the call