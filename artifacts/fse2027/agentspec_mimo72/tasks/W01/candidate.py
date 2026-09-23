def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    parsed = json.loads(tool_input)
    tool_name = user_input.get('tool')
    trusted_labels = user_input.get('trusted_event_labels', [])
    pii_present = 'PII' in trusted_labels
    if tool_name == 'send_reply':
        destination = parsed.get('destination', '')
        diagnostics = parsed.get('diagnostics', False)
        if destination == 'forum' or diagnostics is True:
            if pii_present:
                return True
            else:
                return False
        else:
            return False
    else:
        return False