import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input) if tool_input else {}
    tool_name = user_input.get("tool", "")
    trusted_labels = user_input.get("trusted_event_labels", [])

    # Determine the target slot based on the tool and its parameters
    target_slot = ""
    if tool_name == "summarize":
        target_slot = "slot:notes"
    elif tool_name == "stage":
        target_slot = "slot:staged"
    elif tool_name == "publish":
        target_slot = params.get("target", "")
    else:
        # Unknown tool; policy does not restrict, so allow
        return False

    # Policy: forbidden labels for specific slots
    forbidden_slots = {
        "slot:newsletter": ["CONFIDENTIAL"],
        "slot:website": ["CONFIDENTIAL"]
    }

    if target_slot in forbidden_slots:
        if any(label in trusted_labels for label in forbidden_slots[target_slot]):
            return True  # Stop the tool call

    return False  # Allow the tool call