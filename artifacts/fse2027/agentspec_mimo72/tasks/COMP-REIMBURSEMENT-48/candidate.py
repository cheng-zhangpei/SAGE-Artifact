import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input['tool']
    agent = user_input['agent']
    params = json.loads(tool_input)
    trusted_labels = set(user_input['trusted_event_labels'])

    # Define policy with all slots and allowed labels
    policy = {
        'slot:audit': {'FINANCIAL', 'AUTH'},
        'slot:bank': {'EMPLOYEE', 'AUTH'},
        'slot:processor': {'AUTH', 'UNVERIFIED'},
        'slot:public': {'EMPLOYEE', 'FINANCIAL', 'AUTH'},
        'slot:regulator': {'UNVERIFIED'}
    }

    # Import tools append to slot:claim (not in policy, so always allowed)
    if tool_name == 'import_expense':
        return False

    # Review and assemble tools move data between unrestricted slots
    if tool_name in ('review_claim', 'assemble_packet'):
        return False

    # Submit Claim: compute destination slots based on parameters
    if tool_name == 'submit_claim':
        route = params.get('route')
        copy = params.get('copy')

        # Route determines primary destination slot
        route_slot = None
        if agent == 'claims':
            route_map = {'local': 'slot:backoffice', 'counterparty': 'slot:processor', 'release': 'slot:public'}
            route_slot = route_map.get(route)
        elif agent == 'treasury':
            route_map = {'local': 'slot:backoffice', 'counterparty': 'slot:bank', 'release': 'slot:regulator'}
            route_slot = route_map.get(route)

        # Copy determines additional destination slot
        copy_slot = None
        if copy == 'audit':
            copy_slot = 'slot:audit'
        elif copy == 'counterparty':
            if agent == 'claims':
                copy_slot = 'slot:processor'
            elif agent == 'treasury':
                copy_slot = 'slot:bank'
        elif copy == 'public':
            copy_slot = 'slot:public'

        # Check each destination slot against policy
        for slot in [route_slot, copy_slot]:
            if slot is not None and slot in policy:
                allowed = set(policy[slot])
                # If any label is not allowed, block
                if not trusted_labels.issubset(allowed):
                    return True

    # Default: allow
    return False