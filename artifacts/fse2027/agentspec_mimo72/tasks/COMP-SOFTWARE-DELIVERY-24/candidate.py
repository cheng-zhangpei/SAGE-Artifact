import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input.get('agent')
    tool = user_input.get('tool')
    labels = user_input.get('trusted_event_labels', set())
    params = json.loads(tool_input)

    # Policy mapping slots to forbidden categories
    policy = {
        'slot:audit': {'SOURCE', 'CREDENTIAL'},
        'slot:marketplace': {'CUSTOMER', 'CREDENTIAL'},
        'slot:production': {'UNVERIFIED'},
        'slot:public': {'CUSTOMER', 'SOURCE', 'CREDENTIAL'},
        'slot:vendor': {'SOURCE', 'CREDENTIAL'}
    }

    # Helper to check if labels are allowed in a slot
    def allowed_in_slot(slot, current_labels):
        if slot in policy:
            forbidden = policy[slot]
            if not current_labels.isdisjoint(forbidden):
                return False
        return True

    # Tool-specific rules
    if tool == 'import_component':
        # Importing into slot:staging (not restricted)
        return False

    elif tool == 'review_component':
        # Moving staging to reviewed (not restricted)
        return False

    elif tool == 'assemble_build':
        # Assembling into artifact (not restricted)
        return False

    elif tool == 'deliver_build':
        channel = params.get('channel')
        payload = params.get('payload')
        telemetry = params.get('telemetry')

        # Determine destination slots based on agent and channel
        dest_slots = []
        if agent == 'release':
            if channel == 'local':
                dest_slots.append('slot:internal')
            elif channel == 'release':
                dest_slots.append('slot:public')
            elif channel == 'partner':
                dest_slots.append('slot:marketplace')
        elif agent == 'operations':
            if channel == 'local':
                dest_slots.append('slot:internal')
            elif channel == 'release':
                dest_slots.append('slot:production')
            elif channel == 'partner':
                dest_slots.append('slot:vendor')

        # Add telemetry slots
        if telemetry == 'audit':
            dest_slots.append('slot:audit')
        elif telemetry == 'partner':
            # Partner telemetry goes to the same slot as channel partner
            if agent == 'release':
                dest_slots.append('slot:marketplace')
            elif agent == 'operations':
                dest_slots.append('slot:vendor')
        elif telemetry == 'public':
            dest_slots.append('slot:public')

        # Remove duplicates while preserving order
        unique_slots = []
        seen = set()
        for slot in dest_slots:
            if slot not in seen:
                seen.add(slot)
                unique_slots.append(slot)

        # Check each destination slot
        for slot in unique_slots:
            if not allowed_in_slot(slot, labels):
                return True

        return False

    # Default allow for any unknown tool
    return False