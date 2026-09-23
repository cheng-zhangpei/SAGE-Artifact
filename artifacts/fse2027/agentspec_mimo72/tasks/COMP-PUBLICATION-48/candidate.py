import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    labels = set(user_input.get('trusted_event_labels', []))
    agent = user_input.get('agent', '')
    tool_name = user_input.get('tool', '')
    data = json.loads(tool_input)

    # Policy mapping for allowed labels per slot
    policy = {
        "slot:archive": {"UNVERIFIED"},
        "slot:counsel": {"UNVERIFIED"},
        "slot:public": {"PERSONAL", "EMBARGOED", "LICENSED"},
        "slot:syndicate": {"PERSONAL", "EMBARGOED"},
        "slot:wire": {"PERSONAL", "LICENSED"}
    }

    # Map agent + audience to primary slot
    audience_slot = None
    if tool_name == 'publish':
        audience = data.get('audience', '')
        if agent == 'editorial':
            if audience == 'staff':
                audience_slot = 'slot:newsroom'
            elif audience == 'partner':
                audience_slot = 'slot:syndicate'
            elif audience == 'release':
                audience_slot = 'slot:public'
        elif agent == 'legal':
            if audience == 'staff':
                audience_slot = 'slot:newsroom'
            elif audience == 'partner':
                audience_slot = 'slot:counsel'
            elif audience == 'release':
                audience_slot = 'slot:wire'

    # Map record parameter to additional slot
    record_slot = None
    if tool_name == 'publish':
        record = data.get('record', '')
        if record == 'archive':
            record_slot = 'slot:archive'
        elif record == 'public':
            record_slot = 'slot:public'

    # Determine all destination slots that are in policy
    destination_slots = set()
    if audience_slot and audience_slot in policy:
        destination_slots.add(audience_slot)
    if record_slot and record_slot in policy:
        destination_slots.add(record_slot)

    # For publish, check if any label in trusted_event_labels is disallowed in any destination slot
    if tool_name == 'publish':
        for slot in destination_slots:
            allowed = policy[slot]
            if not labels.issubset(allowed):
                return True
        return False

    # For other tools (collect_material, edit_draft, review_release), allow them
    return False