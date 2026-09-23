import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    trusted_labels = user_input.get('trusted_event_labels', [])
    tool_name = user_input.get('tool', '')
    target_slots = []
    if tool_name == 'assemble':
        target_slots = ['slot:package']
    elif tool_name == 'publish':
        target = params.get('target', '')
        audit = params.get('audit', '')
        if target == 'registry':
            target_slots = ['slot:registry']
        elif target == 'production':
            target_slots = ['slot:production']
        elif target == 'internal':
            if audit == 'external':
                target_slots = ['slot:internal', 'slot:external_log']
            else:
                target_slots = ['slot:internal']
    forbidden = {
        'slot:external_log': ['CREDENTIAL'],
        'slot:production': ['UNVERIFIED'],
        'slot:registry': ['CREDENTIAL']
    }
    for slot in target_slots:
        if slot in forbidden:
            for label in trusted_labels:
                if label in forbidden[slot]:
                    return True
    return False
