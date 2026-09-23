import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    parsed_input = json.loads(tool_input)
    tool_name = user_input.get('tool')
    trusted_labels = user_input.get('trusted_event_labels', [])

    if tool_name == 'submit':
        attachment = parsed_input.get('attachment', 'none')
        index = parsed_input.get('index', False)
        visibility = parsed_input.get('visibility', 'internal')
        if 'TOKEN' in trusted_labels and (visibility == 'public' or index is True):
            return True
        else:
            return False
    else:
        return False