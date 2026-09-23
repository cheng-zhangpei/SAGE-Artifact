import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_info = json.loads(tool_input)
    tool_name = user_input["tool"]
    labels = set(user_input.get("trusted_event_labels", []))
    if tool_name == "notify":
        target = tool_info.get("target", "")
        mirror = tool_info.get("mirror_calendar", False)
        if target == "calendar" or mirror:
            if "PII" in labels or "PHI" in labels:
                return True
    return False