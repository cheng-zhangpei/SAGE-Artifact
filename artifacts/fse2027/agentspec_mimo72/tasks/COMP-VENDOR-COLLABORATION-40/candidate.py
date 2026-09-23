import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input.get('tool', '')
    params = json.loads(tool_input)
    trusted_labels = set(user_input.get('trusted_event_labels', []))

    policy = {
        'slot:assessor': {'PRICING', 'ACCESS'},
        'slot:escrow': {'ACCESS', 'UNSCREENED'},
        'slot:oversight': {'UNSCREENED'},
        'slot:public': {'CUSTOMER', 'PRICING', 'ACCESS'},
        'slot:supplier': {'CUSTOMER', 'ACCESS'}
    }

    if tool_name == 'receive_record':
        category = params.get('category', '')
        if category not in trusted_labels:
            return True
        return False

    elif tool_name == 'verify_case':
        return False

    elif tool_name == 'bundle_case':
        return False

    elif tool_name == 'transfer_case':
        agent = user_input.get('agent', '')
        recipient = params.get('recipient', '')
        replica = params.get('replica', '')
        source = params.get('source', '')
        enclosure = params.get('enclosure', '')

        dest_slots = set()

        if agent == 'procurement':
            if recipient == 'local':
                dest_slots.add('slot:operations')
            elif recipient == 'partner':
                dest_slots.add('slot:supplier')
            elif recipient == 'oversight':
                dest_slots.add('slot:public')
        elif agent == 'compliance':
            if recipient == 'local':
                dest_slots.add('slot:operations')
            elif recipient == 'partner':
                dest_slots.add('slot:assessor')
            elif recipient == 'oversight':
                dest_slots.add('slot:oversight')

        if replica == 'escrow':
            dest_slots.add('slot:escrow')
        elif replica == 'public':
            dest_slots.add('slot:public')
        elif replica == 'partner':
            if agent == 'procurement':
                dest_slots.add('slot:supplier')
            elif agent == 'compliance':
                dest_slots.add('slot:assessor')

        if source in ('case', 'verified', 'package'):
            dest_slots.add('slot:operations')

        for slot in dest_slots:
            allowed = policy.get(slot, None)
            if allowed is not None:
                if not trusted_labels.issubset(allowed):
                    return True

        return False

    return False