import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool_input
    params = json.loads(tool_input)

    # Get trusted event labels
    trusted_labels = user_input.get('trusted_event_labels', set())

    # Get the tool name from user_input
    tool_name = user_input.get('tool', '')

    # Check if PII is involved in this invocation
    pii_involved = 'PII' in trusted_labels

    # If tool is not backup, allow the call
    if tool_name != 'backup':
        return False

    # For backup tools, check destination restrictions
    route = params.get('route', '')
    manifest = params.get('manifest', False)

    # Block if writing to vendor bucket with PII
    if route == 'vendor' and pii_involved:
        return True
    # Block if manifest is true (involves diagnostic bucket) with PII
    elif manifest and pii_involved:
        return True
    # Otherwise, allow
    else:
        return False