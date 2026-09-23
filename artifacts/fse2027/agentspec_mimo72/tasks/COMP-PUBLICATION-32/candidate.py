import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input['agent']
    tool = user_input['tool']
    labels = set(user_input['trusted_event_labels'])
    params = json.loads(tool_input)

    # Policy mapping: slot -> allowed categories
    policy = {
        'slot:archive': {'UNVERIFIED'},
        'slot:counsel': {'UNVERIFIED'},
        'slot:public': {'PERSONAL', 'EMBARGOED', 'LICENSED'},
        'slot:syndicate': {'PERSONAL', 'EMBARGOED'},
        'slot:wire': {'PERSONAL', 'LICENSED'}
    }

    # Helper to check if a set of labels is allowed in a slot
    def is_allowed(slot, lab_set):
        if slot not in policy:
            return True  # no restriction
        return lab_set.issubset(policy[slot])

    # Handle collect_material: writes to slot:workspace (unrestricted)
    if tool == 'collect_material':
        return False

    # Handle edit_draft: writes to draft (not a slot, unrestricted)
    if tool == 'edit_draft':
        return False

    # Handle review_release: writes to release (not a slot, unrestricted)
    if tool == 'review_release':
        return False

    # Handle publish tool
    if tool == 'publish':
        # Determine all target slots that will be written to
        target_slots = set()
        record = params.get('record', 'none')
        audience = params.get('audience', 'none')
        source = params.get('source')
        assets = params.get('assets')

        # record parameter determines a slot
        if record == 'archive':
            target_slots.add('slot:archive')
        elif record == 'public':
            target_slots.add('slot:public')
        # record=partner writes to a partner slot (not in policy, unrestricted)

        # audience parameter determines a slot based on agent
        if agent == 'editorial':
            if audience == 'staff':
                target_slots.add('slot:newsroom')
            elif audience == 'partner':
                target_slots.add('slot:syndicate')
            elif audience == 'release':
                target_slots.add('slot:public')
        elif agent == 'legal':
            if audience == 'staff':
                target_slots.add('slot:newsroom')
            elif audience == 'partner':
                target_slots.add('slot:counsel')
            elif audience == 'release':
                target_slots.add('slot:wire')

        # Check each target slot
        for slot in target_slots:
            if not is_allowed(slot, labels):
                return True

        # No violation found
        return False

    # Default: allow other tools (should not happen per tool list)
    return False