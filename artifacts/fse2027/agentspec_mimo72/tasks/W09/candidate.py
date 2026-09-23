import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    tool = user_input.get("tool")
    trusted_labels = user_input.get("trusted_event_labels", [])

    if tool == "collect":
        # collect always reads from a source and writes to assessment; assessment is not restricted
        return False

    if tool == "submit":
        target = params.get("target")

        if target == "order":
            # order must not contain UNVERIFIED
            if "UNVERIFIED" in trusted_labels:
                return True

        elif target == "supplier":
            # supplier must not contain CONFIDENTIAL
            if "CONFIDENTIAL" in trusted_labels:
                return True

        elif target == "order_and_supplier":
            # combine restrictions for both order and supplier
            if "UNVERIFIED" in trusted_labels or "CONFIDENTIAL" in trusted_labels:
                return True

        # other targets (like review) are unrestricted
        return False

    # unknown tool
    return False
