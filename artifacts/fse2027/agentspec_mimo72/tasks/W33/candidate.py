import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    target = params.get('target')
    trusted_labels = set(user_input.get('trusted_event_labels', []))

    restrictions = {
        'acoustic': {'PII'},
        'text_vendor': {'BIOMETRIC'}
    }

    if target == 'both':
        destinations = ['acoustic', 'text_vendor']
    else:
        destinations = [target]

    for dest in destinations:
        forbidden = restrictions.get(dest, set())
        if not trusted_labels.isdisjoint(forbidden):
            return True

    return False