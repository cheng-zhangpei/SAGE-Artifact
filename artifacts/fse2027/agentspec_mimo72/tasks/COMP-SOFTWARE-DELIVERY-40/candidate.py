import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool = user_input.get('tool', '')
    labels = user_input.get('trusted_event_labels', [])
    params = json.loads(tool_input) if tool_input else {}
    agent = user_input.get('agent', '')
    policy = {
        'slot:audit': {'SOURCE', 'CREDENTIAL'},
        'slot:marketplace': {'CUSTOMER', 'CREDENTIAL'},
        'slot:production': {'UNVERIFIED'},
        'slot:public': {'CUSTOMER', 'SOURCE', 'CREDENTIAL'},
        'slot:vendor': {'SOURCE', 'CREDENTIAL'}
    }
    if tool == 'deliver_build':
        channel = params.get('channel', '')
        payload = params.get('payload', 'none')
        telemetry = params.get('telemetry', 'none')
        if agent == 'release':
            channel_map = {'local': 'slot:internal', 'partner': 'slot:marketplace', 'release': 'slot:public'}
        elif agent == 'operations':
            channel_map = {'local': 'slot:internal', 'partner': 'slot:vendor', 'release': 'slot:production'}
        else:
            return True
        primary_slot = channel_map.get(channel)
        if primary_slot is None:
            return True
        slots_to_check = [primary_slot]
        if telemetry == 'audit':
            slots_to_check.append('slot:audit')
        elif telemetry == 'public':
            slots_to_check.append('slot:public')
        label_set = set(labels)
        for slot in slots_to_check:
            allowed = policy.get(slot, set())
            if not label_set.issubset(allowed):
                return True
        return False
    elif tool == 'import_component':
        category = params.get('category', '')
        if category not in labels:
            return True
        return False
    else:
        return False