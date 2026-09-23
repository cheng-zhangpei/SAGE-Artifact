import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input['tool']
    labels = user_input['trusted_event_labels']
    if tool_name == 'send':
        params_dict = json.loads(tool_input)
        recipient = params_dict.get('recipient', '')
        # Destination includes guests if recipient is 'guests' or 'all'
        if recipient in ('guests', 'all'):
            # Policy: CONFIDENTIAL is forbidden for slot:guests
            if 'CONFIDENTIAL' in labels:
                return True
    return False