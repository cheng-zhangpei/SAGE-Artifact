import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool_name = user_input.get("tool")
    trusted_labels = set(user_input.get("trusted_event_labels", []))
    allowed_labels = {
        "room": {"PII", "VALUATION", "TOKEN"},
        "counsel": {"PII", "VALUATION"},
        "investors": set(),
        "notifications": {"VALUATION"}
    }
    if tool_name in ["collect", "create_access"]:
        return False
    elif tool_name == "deliver":
        target = params.get("target")
        email_copy = params.get("email_copy", False)
        destinations = [target]
        if email_copy:
            destinations.append("notifications")
        for dest in destinations:
            if dest in allowed_labels:
                allowed = allowed_labels[dest]
                if any(label not in allowed for label in trusted_labels):
                    return True
        return False
    else:
        return True