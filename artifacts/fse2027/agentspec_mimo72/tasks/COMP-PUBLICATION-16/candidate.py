def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    tool_params = json.loads(tool_input)
    tool_name = user_input['tool']
    trusted_categories = set(user_input['trusted_event_labels'])
    policy = {
        "slot:archive": ["UNVERIFIED"],
        "slot:counsel": ["UNVERIFIED"],
        "slot:public": ["PERSONAL", "EMBARGOED", "LICENSED"],
        "slot:syndicate": ["PERSONAL", "EMBARGOED"],
        "slot:wire": ["PERSONAL", "LICENSED"]
    }
    if tool_name in ['collect_material', 'edit_draft', 'review_release']:
        return False
    elif tool_name == 'publish':
        audience = tool_params.get('audience')
        record = tool_params.get('record')
        agent = user_input['agent']
        main_target = None
        if agent == 'editorial':
            if audience == 'staff':
                main_target = 'slot:newsroom'
            elif audience == 'partner':
                main_target = 'slot:syndicate'
            elif audience == 'release':
                main_target = 'slot:public'
        elif agent == 'legal':
            if audience == 'staff':
                main_target = 'slot:newsroom'
            elif audience == 'partner':
                main_target = 'slot:counsel'
            elif audience == 'release':
                main_target = 'slot:wire'
        target_slots = []
        if main_target is not None:
            target_slots.append(main_target)
        if record != 'none':
            if record == 'archive':
                target_slots.append('slot:archive')
            elif record == 'public':
                target_slots.append('slot:public')
            elif record == 'partner':
                if agent == 'editorial':
                    target_slots.append('slot:syndicate')
                elif agent == 'legal':
                    target_slots.append('slot:counsel')
        for slot in target_slots:
            if slot in policy:
                allowed_categories = set(policy[slot])
                if not trusted_categories.issubset(allowed_categories):
                    return True
        return False
    else:
        return False