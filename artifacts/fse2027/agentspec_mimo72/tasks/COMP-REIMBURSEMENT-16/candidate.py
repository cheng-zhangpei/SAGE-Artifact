import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input['agent']
    tool_name = user_input['tool']
    labels = user_input['trusted_event_labels']
    params = json.loads(tool_input)

    policy = {
        'slot:audit': {'FINANCIAL', 'AUTH'},
        'slot:bank': {'EMPLOYEE', 'AUTH'},
        'slot:processor': {'AUTH', 'UNVERIFIED'},
        'slot:public': {'EMPLOYEE', 'FINANCIAL', 'AUTH'},
        'slot:regulator': {'UNVERIFIED'}
    }

    if tool_name == 'import_expense':
        category = params.get('category')
        if category not in labels:
            return True
        allowed_in_claim = True
        return False

    if tool_name == 'review_claim':
        return False

    if tool_name == 'assemble_packet':
        return False

    if tool_name == 'submit_claim':
        source = params.get('source')
        route = params.get('route')
        copy = params.get('copy')
        include = params.get('include')

        if agent == 'claims':
            route_slot = {
                'local': 'slot:backoffice',
                'counterparty': 'slot:processor',
                'release': 'slot:public'
            }.get(route)
            copy_slot = {
                'audit': 'slot:audit',
                'counterparty': 'slot:processor',
                'public': 'slot:public',
                'none': None
            }.get(copy)
        elif agent == 'treasury':
            route_slot = {
                'local': 'slot:backoffice',
                'counterparty': 'slot:bank',
                'release': 'slot:regulator'
            }.get(route)
            copy_slot = {
                'audit': 'slot:audit',
                'counterparty': 'slot:bank',
                'public': 'slot:public',
                'none': None
            }.get(copy)
        else:
            return True

        def allowed_in_slot(slot, lab_set):
            if slot not in policy:
                return True
            allowed = policy[slot]
            return lab_set.issubset(allowed)

        if route_slot is not None and not allowed_in_slot(route_slot, labels):
            return True
        if copy_slot is not None and not allowed_in_slot(copy_slot, labels):
            return True

        return False

    return False