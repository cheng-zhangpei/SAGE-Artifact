import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool parameters
    params = json.loads(tool_input)
    agent = user_input['agent']
    tool = user_input['tool']
    trusted_labels = user_input['trusted_event_labels']

    # Define the policy for restricted slots
    policy = {
        "slot:review": ["ADDRESS", "HEALTH"],
        "slot:rider": ["HEALTH"]
    }

    # Check if this is a dispatcher send tool targeting a restricted slot
    if agent == "dispatcher" and tool == "send":
        target = params.get("target")
        if target:
            slot_key = "slot:" + target
            if slot_key in policy:
                forbidden = set(policy[slot_key])
                # Stop if any trusted label is forbidden for this slot
                if set(trusted_labels).intersection(forbidden):
                    return True

    # Allow all other tool calls
    return False
