import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse the tool input to extract parameters
    params = json.loads(tool_input)
    # Get the target from parameters if present
    target = params.get('target')
    # Check if the target is the restricted slot 'machine'
    if target == "machine":
        # Get the source from parameters
        source = params.get('source')
        # Only block if the source is 'plan' and UNVERIFIED is in trusted event labels
        if source == "plan":
            trusted_labels = user_input.get('trusted_event_labels', {})
            if "UNVERIFIED" in trusted_labels:
                return True  # Stop the call to prevent UNVERIFIED in machine
    # Allow all other tool calls, including read-only manual on machine
    return False