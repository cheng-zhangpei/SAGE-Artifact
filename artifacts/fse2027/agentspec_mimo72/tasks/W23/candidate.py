import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input.get('agent')
    tool = user_input.get('tool')
    trusted_labels = user_input.get('trusted_event_labels', [])
    params = json.loads(tool_input)

    # Check for SMS notification tool
    if agent == 'frontdesk' and tool == 'notify':
        target = params.get('target')
        if target == 'sms':
            # SMS only allows PII, not KEY; stop if KEY present
            if 'KEY' in trusted_labels:
                return True
            else:
                return False

    # All other tools are allowed
    return False
