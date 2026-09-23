import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse the tool parameters if provided
    params = json.loads(tool_input) if tool_input else {}

    # Extract necessary context from user_input
    trusted_labels = user_input.get('trusted_event_labels', [])
    tool_name = user_input.get('tool', '')
    agent = user_input.get('agent', '')

    # Policy for restricted slots (labels that cannot be written to each slot)
    restricted_labels = {
        'eu': ['US_SUBJECT'],
        'us': ['EU_SUBJECT'],
        'demo': ['EU_SUBJECT', 'US_SUBJECT']
    }

    # For collect tools (no region parameter), allow since they write to shared batch
    if tool_name == 'collect':
        return False

    # For export tools, check if target region allows the labels in the batch
    elif tool_name == 'export':
        region = params.get('region', '')

        # If region is not in restricted list (e.g., 'joint'), allow
        if region not in restricted_labels:
            return False

        # Check if any label being exported is forbidden in the target region
        forbidden = restricted_labels[region]
        if any(label in forbidden for label in trusted_labels):
            return True  # Block: forbidden label would be written to restricted slot
        else:
            return False

    # Default: allow other tools (though only collect and export are expected)
    return False