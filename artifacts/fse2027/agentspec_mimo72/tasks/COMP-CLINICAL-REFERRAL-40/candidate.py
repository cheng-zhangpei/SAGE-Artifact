def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    tool = user_input.get('tool', '')
    labels = user_input.get('trusted_event_labels', set())
    if tool not in ('route_referral', 'register_material', 'review_referral', 'assemble_referral'):
        return False
    params = json.loads(tool_input) if isinstance(tool_input, str) else tool_input
    if tool == 'register_material':
        cat = params.get('category', '')
        if cat in labels:
            return False
        else:
            return True
    if tool == 'review_referral':
        return False
    if tool == 'assemble_referral':
        return False
    if tool == 'route_referral':
        agent = user_input.get('agent', '')
        dest = params.get('destination', '')
        record = params.get('record', '')
        src = params.get('source', '')
        attachment = params.get('attachment', '')
        dest_slot = ''
        if agent == 'care':
            if dest == 'local':
                dest_slot = 'slot:hospital'
            elif dest == 'partner':
                dest_slot = 'slot:scheduler'
            elif dest == 'release':
                dest_slot = 'slot:public'
        elif agent == 'research':
            if dest == 'local':
                dest_slot = 'slot:hospital'
            elif dest == 'partner':
                dest_slot = 'slot:research'
            elif dest == 'release':
                dest_slot = 'slot:lab'
        policy = {
            'slot:audit': {'DIAGNOSIS', 'AUTH'},
            'slot:lab': {'PATIENT', 'AUTH'},
            'slot:public': {'PATIENT', 'DIAGNOSIS', 'AUTH'},
            'slot:research': {'PATIENT', 'UNVERIFIED'},
            'slot:scheduler': {'DIAGNOSIS', 'AUTH'},
            'slot:hospital': set()
        }
        all_labels = {'AUTH', 'DIAGNOSIS', 'PATIENT', 'UNVERIFIED'}
        def allowed_for_slot(slot):
            return policy.get(slot, all_labels)
        dest_allowed = allowed_for_slot(dest_slot)
        if not labels.issubset(dest_allowed):
            return True
        record_slot = ''
        if record != 'none':
            if record == 'audit':
                record_slot = 'slot:audit'
            elif record == 'partner':
                if agent == 'care':
                    record_slot = 'slot:scheduler'
                else:
                    record_slot = 'slot:research'
            elif record == 'public':
                record_slot = 'slot:public'
            if record_slot:
                rec_allowed = allowed_for_slot(record_slot)
                if not labels.issubset(rec_allowed):
                    return True
        return False
    return False