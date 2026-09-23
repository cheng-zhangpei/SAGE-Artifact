def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    params = json.loads(tool_input)
    labels = user_input['trusted_event_labels']
    tool = user_input['tool']
    agent = user_input['agent']

    policy = {
        'slot:archive': ['UNVERIFIED'],
        'slot:counsel': ['UNVERIFIED'],
        'slot:public': ['PERSONAL', 'EMBARGOED', 'LICENSED'],
        'slot:syndicate': ['PERSONAL', 'EMBARGOED'],
        'slot:wire': ['PERSONAL', 'LICENSED']
    }

    if tool in ['collect_material', 'edit_draft', 'review_release']:
        return False
    elif tool == 'publish':
        audience = params.get('audience')
        record = params.get('record')
        primary_slot = None
        if agent == 'editorial':
            if audience == 'staff':
                primary_slot = 'slot:newsroom'
            elif audience == 'partner':
                primary_slot = 'slot:syndicate'
            elif audience == 'release':
                primary_slot = 'slot:public'
        elif agent == 'legal':
            if audience == 'staff':
                primary_slot = 'slot:newsroom'
            elif audience == 'partner':
                primary_slot = 'slot:counsel'
            elif audience == 'release':
                primary_slot = 'slot:wire'
        additional_slot = None
        if record == 'archive':
            additional_slot = 'slot:archive'
        elif record == 'public':
            additional_slot = 'slot:public'
        elif record == 'partner':
            additional_slot = 'slot:partner'
        target_slots = set()
        if primary_slot:
            target_slots.add(primary_slot)
        if additional_slot:
            target_slots.add(additional_slot)
        label_set = set(labels) if not isinstance(labels, set) else labels
        for slot in target_slots:
            if slot in policy:
                allowed_set = set(policy[slot])
                if not label_set.issubset(allowed_set):
                    return True
        return False
    else:
        return False