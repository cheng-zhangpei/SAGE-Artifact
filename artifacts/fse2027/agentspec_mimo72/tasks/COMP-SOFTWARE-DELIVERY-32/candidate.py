import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool = user_input.get('tool', '')
    agent = user_input.get('agent', '')
    labels = set(user_input.get('trusted_event_labels', []))
    params = json.loads(tool_input)

    # Policy map: slot -> set of prohibited labels
    policy = {
        'slot:audit': {'SOURCE', 'CREDENTIAL'},
        'slot:marketplace': {'CUSTOMER', 'CREDENTIAL'},
        'slot:production': {'UNVERIFIED'},
        'slot:public': {'CUSTOMER', 'SOURCE', 'CREDENTIAL'},
        'slot:vendor': {'SOURCE', 'CREDENTIAL'}
    }

    # Tool-specific logic
    if tool == 'import_component':
        # Writes to slot:staging, not in policy -> always allowed
        return False

    elif tool == 'review_component':
        # Appends staging to reviewed; slot:reviewed not in policy -> allowed
        return False

    elif tool == 'assemble_build':
        # Appends to slot:artifact; not in policy -> allowed
        return False

    elif tool == 'deliver_build':
        channel = params.get('channel', '')
        payload = params.get('payload', '')
        source = params.get('source', '')
        telemetry = params.get('telemetry', '')

        # Determine main destination slot from channel and agent
        main_dest = None
        if agent == 'release':
            if channel == 'local':
                main_dest = 'slot:internal'
            elif channel == 'release':
                main_dest = 'slot:marketplace'
            elif channel == 'partner':
                main_dest = 'slot:public'
        elif agent == 'operations':
            if channel == 'local':
                main_dest = 'slot:internal'
            elif channel == 'release':
                main_dest = 'slot:vendor'
            elif channel == 'partner':
                main_dest = 'slot:production'

        # Collect all destination slots to check
        check_slots = []
        if main_dest in policy:
            check_slots.append(main_dest)
        if telemetry == 'audit' and 'slot:audit' in policy:
            check_slots.append('slot:audit')
        if telemetry == 'public' and 'slot:public' in policy:
            check_slots.append('slot:public')

        # Check if any prohibited label in current labels is present
        for slot in check_slots:
            if not labels.isdisjoint(policy[slot]):
                return True  # block
        return False  # allow

    # Unknown tool: allow (policy doesn't forbid it)
    return False