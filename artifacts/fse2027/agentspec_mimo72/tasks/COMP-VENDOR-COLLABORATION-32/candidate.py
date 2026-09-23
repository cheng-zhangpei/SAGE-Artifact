import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool = user_input.get('tool')
    agent = user_input.get('agent')
    trusted_labels = user_input.get('trusted_event_labels')
    trusted_set = set(trusted_labels) if trusted_labels else set()
    policy = {
        'slot:assessor': {'PRICING', 'ACCESS'},
        'slot:escrow': {'ACCESS', 'UNSCREENED'},
        'slot:oversight': {'UNSCREENED'},
        'slot:public': {'CUSTOMER', 'PRICING', 'ACCESS'},
        'slot:supplier': {'CUSTOMER', 'ACCESS'}
    }
    if tool in ['receive_record', 'verify_case', 'bundle_case']:
        return False
    elif tool == 'transfer_case':
        destination_slots = set()
        recipient = params.get('recipient')
        if agent == 'procurement':
            if recipient == 'local':
                destination_slots.add('slot:operations')
            elif recipient == 'partner':
                destination_slots.add('slot:supplier')
            elif recipient == 'oversight':
                destination_slots.add('slot:public')
        elif agent == 'compliance':
            if recipient == 'local':
                destination_slots.add('slot:operations')
            elif recipient == 'partner':
                destination_slots.add('slot:assessor')
            elif recipient == 'oversight':
                destination_slots.add('slot:oversight')
        replica = params.get('replica')
        if replica == 'escrow':
            destination_slots.add('slot:escrow')
        elif replica == 'public':
            destination_slots.add('slot:public')
        elif replica == 'partner':
            if agent == 'procurement':
                destination_slots.add('slot:supplier')
            elif agent == 'compliance':
                destination_slots.add('slot:assessor')
        for slot in destination_slots:
            if slot in policy:
                if not trusted_set.issubset(policy[slot]):
                    return True
        return False
    else:
        return False