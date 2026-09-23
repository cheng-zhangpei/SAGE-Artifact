def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    tool = user_input.get("tool", "")
    labels = user_input.get("trusted_event_labels", set())
    label_set = set(labels)
    params = json.loads(tool_input) if tool_input else {}
    target = params.get("target", None)
    if tool == "send":
        if target == "listing":
            if not label_set.issubset({"PII", "ACCESS_CODE"}):
                return True
        elif target == "sms":
            if not label_set.issubset({"ACCESS_CODE"}):
                return True
    elif tool == "issue":
        if target == "sms":
            if not label_set.issubset({"ACCESS_CODE"}):
                return True
    return False