import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input["tool"]
    trusted_labels = set(user_input["trusted_event_labels"])
    params = json.loads(tool_input)

    if tool_name == "collect":
        return False
    if tool_name == "stage":
        return False
    if tool_name == "announce":
        attachments = params["attachments"]
        target = params["target"]
        if not attachments:
            return False
        if target == "status":
            if "PII" in trusted_labels and "CREDENTIAL" in trusted_labels:
                return True
            else:
                return False
        elif target == "coordinator":
            if "CREDENTIAL" in trusted_labels:
                return True
            else:
                return False
        elif target == "response_room":
            return False
        else:
            return False
    return False