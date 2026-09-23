import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse inputs
    tool_name = user_input.get('tool')
    agent = user_input.get('agent')
    trusted_labels = user_input.get('trusted_event_labels', [])
    trusted_set = set(trusted_labels)
    params = json.loads(tool_input) if tool_input else {}

    # Only submit_claim tools may write to restricted slots
    if tool_name != 'submit_claim':
        return False

    # Determine destination slots based on agent and parameters
    route = params.get('route', '')
    copy = params.get('copy', 'none')

    main_slot = None
    if agent == 'claims':
        if route == 'local':
            main_slot = 'slot:backoffice'
        elif route == 'counterparty':
            main_slot = 'slot:processor'
        elif route == 'release':
            main_slot = 'slot:public'
    elif agent == 'treasury':
        if route == 'local':
            main_slot = 'slot:backoffice'
        elif route == 'counterparty':
            main_slot = 'slot:bank'
        elif route == 'release':
            main_slot = 'slot:regulator'

    copy_slots = set()
    if copy == 'audit':
        copy_slots.add('slot:audit')
    elif copy == 'public':
        copy_slots.add('slot:public')
    elif copy == 'counterparty':
        if agent == 'claims':
            copy_slots.add('slot:processor')
        elif agent == 'treasury':
            copy_slots.add('slot:bank')

    dest_slots = set()
    if main_slot is not None:
        dest_slots.add(main_slot)
    dest_slots.update(copy_slots)

    # Allowed labels per restricted slot from policy
    allowed = {
        'slot:audit': {'FINANCIAL', 'AUTH'},
        'slot:bank': {'EMPLOYEE', 'AUTH'},
        'slot:processor': {'AUTH', 'UNVERIFIED'},
        'slot:public': {'EMPLOYEE', 'FINANCIAL', 'AUTH'},
        'slot:regulator': {'UNVERIFIED'},
    }

    # Check if any destination slot receives disallowed categories
    for slot in dest_slots:
        if slot in allowed:  # slot is restricted
            if not trusted_set.issubset(allowed[slot]):
                return True

    return False