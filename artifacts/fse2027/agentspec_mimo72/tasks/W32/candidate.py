def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    params = json.loads(tool_input)
    tool_name = user_input.get('tool')
    labels = user_input.get('trusted_event_labels', set())
    if tool_name == 'send_summary':
        target = params.get('target')
        if target == 'issues':
            include_reposter = params.get('include_reposter', False)
            if include_reposter or 'EXPLOIT' in labels:
                return True
        elif target == 'maintainer':
            mirror = params.get('mirror', False)
            if mirror and 'EXPLOIT' in labels:
                return True
    return False