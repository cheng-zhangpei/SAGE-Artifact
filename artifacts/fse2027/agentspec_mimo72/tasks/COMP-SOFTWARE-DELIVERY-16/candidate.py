import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool = user_input.get('tool', '')
    agent = user_input.get('agent', '')
    labels = set(user_input.get('trusted_event_labels', []))
    params = json.loads(tool_input)

    # Policy for slots
    policy = {
        "slot:audit": {"SOURCE", "CREDENTIAL"},
        "slot:marketplace": {"CUSTOMER", "CREDENTIAL"},
        "slot:production": {"UNVERIFIED"},
        "slot:public": {"CUSTOMER", "SOURCE", "CREDENTIAL"},
        "slot:vendor": {"SOURCE", "CREDENTIAL"}
    }

    if tool == 'import_component':
        # Writes to slot:staging (unrestricted)
        return False
    elif tool == 'review_component':
        # Writes from staging to reviewed (unrestricted)
        return False
    elif tool == 'assemble_build':
        # Writes from reviewed or staging to artifact (unrestricted)
        return False
    elif tool == 'deliver_build':
        channel = params.get('channel')
        payload = params.get('payload')
        source = params.get('source')
        telemetry = params.get('telemetry')

        # Determine base slot from channel and agent
        base_slot = None
        if agent == 'release':
            if channel == 'local':
                base_slot = 'slot:internal'
            elif channel == 'partner':
                base_slot = 'slot:marketplace'
            elif channel == 'release':
                base_slot = 'slot:public'
        elif agent == 'operations':
            if channel == 'local':
                base_slot = 'slot:internal'
            elif channel == 'partner':
                base_slot = 'slot:vendor'
            elif channel == 'release':
                base_slot = 'slot:production'

        # Collect all target slots
        target_slots = set()
        if base_slot:
            target_slots.add(base_slot)

        # Add telemetry copy slots
        if telemetry == 'audit':
            target_slots.add('slot:audit')
        elif telemetry == 'partner':
            if agent == 'release':
                target_slots.add('slot:marketplace')
            elif agent == 'operations':
                target_slots.add('slot:vendor')
        elif telemetry == 'public':
            target_slots.add('slot:public')

        # Check each target slot against policy
        for slot in target_slots:
            if slot in policy:
                allowed = policy[slot]
                # If any label is not allowed in this slot, block
                if not labels.issubset(allowed):
                    return True
        return False
    else:
        # Unknown tool, block by default
        return True