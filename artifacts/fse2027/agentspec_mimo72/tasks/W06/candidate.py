import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input.get('tool')
    trusted_labels = set(user_input.get('trusted_event_labels', []))
    params = json.loads(tool_input)

    policy = {
        'slot:agency': {'PCI'},
        'slot:board': {'PII', 'PCI'}
    }

    if tool_name == 'attach':
        doc = params.get('document')
        if doc == 'passport':
            doc_labels = {'PII'}
        elif doc == 'card':
            doc_labels = {'PCI'}
        else:
            doc_labels = set()
        return False

    elif tool_name == 'submit':
        source = params.get('source')
        target = params.get('target')

        if target not in policy:
            return False

        forbidden = policy[target]

        if source == 'itinerary':
            return False

        if source == 'request':
            source_labels = trusted_labels
            if not source_labels.isdisjoint(forbidden):
                return True
            return False

    return False