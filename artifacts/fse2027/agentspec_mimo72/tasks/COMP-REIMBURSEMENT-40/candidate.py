import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse the tool_input JSON
    try:
        params = json.loads(tool_input)
    except (json.JSONDecodeError, TypeError):
        return False

    agent = user_input.get('agent', '')
    tool = user_input.get('tool', '')
    trusted_labels = set(user_input.get('trusted_event_labels', []))

    # Policy for slot data categories
    policy = {
        'slot:audit': {'FINANCIAL', 'AUTH'},
        'slot:bank': {'EMPLOYEE', 'AUTH'},
        'slot:processor': {'AUTH', 'UNVERIFIED'},
        'slot:public': {'EMPLOYEE', 'FINANCIAL', 'AUTH'},
        'slot:regulator': {'UNVERIFIED'}
    }

    # For import_expense: check that the category being imported is allowed in slot:claim
    # Since slot:claim is not in policy, all categories are allowed. Return False (allow).
    if tool == 'import_expense':
        return False

    # For review_claim and assemble_packet: these move data between slots not in policy
    if tool in ['review_claim', 'assemble_packet']:
        return False

    # For submit_claim: complex logic
    if tool == 'submit_claim':
        route = params.get('route', '')
        source = params.get('source', '')
        include = params.get('include', 'none')
        copy = params.get('copy', 'none')

        # Determine destination slots based on agent and route
        if agent == 'claims':
            route_map = {'local': 'slot:backoffice', 'counterparty': 'slot:processor', 'release': 'slot:public'}
            copy_map = {'audit': 'slot:audit', 'counterparty': 'slot:processor', 'public': 'slot:public'}
        elif agent == 'treasury':
            route_map = {'local': 'slot:backoffice', 'counterparty': 'slot:bank', 'release': 'slot:regulator'}
            copy_map = {'audit': 'slot:audit', 'counterparty': 'slot:bank', 'public': 'slot:public'}
        else:
            return False

        # Determine which data categories will be sent to destinations
        # Source data: from source slot (or handbook which has no restricted data)
        source_labels = set()
        if source == 'handbook':
            source_labels = set()  # handbook has no restricted data
        elif source == 'approved':
            # We don't know exact labels in approved; we must assume worst case based on policy
            # For safety, assume all categories that could be in approved (derived from claim)
            source_labels = {'EMPLOYEE', 'FINANCIAL', 'AUTH', 'UNVERIFIED'}
        elif source == 'packet':
            source_labels = {'EMPLOYEE', 'FINANCIAL', 'AUTH', 'UNVERIFIED'}
        else:
            source_labels = set()

        # Include additional data
        include_labels = set()
        if include == 'packet':
            include_labels = {'EMPLOYEE', 'FINANCIAL', 'AUTH', 'UNVERIFIED'}
        elif include == 'claim':
            include_labels = {'EMPLOYEE', 'FINANCIAL', 'AUTH', 'UNVERIFIED'}

        # Combined data to send
        combined = source_labels.union(include_labels)

        # Check route destination
        route_dest = route_map.get(route, '')
        if route_dest in policy:
            allowed = policy[route_dest]
            if not combined.issubset(allowed):
                return True  # block

        # Check copy destination if copy is not none
        if copy != 'none':
            copy_dest = copy_map.get(copy, '')
            if copy_dest in policy:
                allowed = policy[copy_dest]
                if not combined.issubset(allowed):
                    return True  # block

        return False

    return False