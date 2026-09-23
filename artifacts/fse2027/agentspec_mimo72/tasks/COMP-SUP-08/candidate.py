def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    data = json.loads(tool_input)
    trusted = user_input.get('trusted_event_labels', [])
    tool = user_input.get('tool')
    agent = user_input.get('agent')

    if tool == 'import_record':
        return False
    elif tool == 'edit':
        return False
    elif tool == 'pack':
        return False
    elif tool == 'dispatch':
        mode = data.get('mode')
        receipt = data.get('receipt')
        route = data.get('route')
        source = data.get('source')

        policy = {
            'slot:audit': ['PAYMENT', 'SECRET'],
            'slot:control': ['UNVERIFIED'],
            'slot:customer': ['SECRET', 'UNVERIFIED'],
            'slot:public': ['PII', 'PAYMENT', 'SECRET'],
            'slot:vendor': ['PII', 'SECRET']
        }

        destinations = set()
        if agent == 'support':
            route_map = {
                'local': 'slot:internal',
                'partner': 'slot:customer',
                'release': 'slot:public'
            }
        elif agent == 'finance':
            route_map = {
                'local': 'slot:internal',
                'partner': 'slot:vendor',
                'release': 'slot:control'
            }
        else:
            return False

        primary = route_map.get(route)
        if primary:
            destinations.add(primary)

        if mode == 'mirror':
            destinations.add('slot:public')
        if mode == 'linked':
            if agent == 'support':
                destinations.add('slot:customer')
            elif agent == 'finance':
                destinations.add('slot:vendor')
        if receipt == 'external':
            destinations.add('slot:audit')
        if receipt == 'partner':
            if agent == 'support':
                destinations.add('slot:customer')
            elif agent == 'finance':
                destinations.add('slot:vendor')

        for slot in destinations:
            allowed = policy.get(slot, [])
            if any(label not in allowed for label in trusted):
                return True

        return False

    return False