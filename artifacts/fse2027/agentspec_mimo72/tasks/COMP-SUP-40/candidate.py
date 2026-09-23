import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool_input to get parameters
    params = json.loads(tool_input)

    # Get tool name from user_input
    tool_name = user_input.get("tool", "")

    # If tool is not dispatch, return False (allow) as only dispatch can cause violations
    if tool_name != "dispatch":
        return False

    # Get agent from user_input
    agent = user_input.get("agent", "")

    # Get dispatch parameters
    mode = params.get("mode", "standard")
    receipt = params.get("receipt", "local")
    route = params.get("route", "local")

    # Determine primary destination slot based on agent and route
    if agent == "support":
        if route == "local":
            primary = "slot:internal"
        elif route == "partner":
            primary = "slot:customer"
        elif route == "release":
            primary = "slot:public"
        else:
            primary = "slot:internal"  # default for invalid route
    elif agent == "finance":
        if route == "local":
            primary = "slot:internal"
        elif route == "partner":
            primary = "slot:vendor"
        elif route == "release":
            primary = "slot:control"
        else:
            primary = "slot:internal"
    else:
        primary = "slot:internal"  # fallback for unknown agent

    # Determine partner address for linked mode and receipt=partner
    if agent == "support":
        partner_addr = "slot:customer"
    elif agent == "finance":
        partner_addr = "slot:vendor"
    else:
        partner_addr = "slot:internal"

    # Compute set of all destination slots
    dest_set = {primary}
    if mode == "mirror":
        dest_set = dest_set.union({"slot:public"})
    if mode == "linked":
        dest_set = dest_set.union({partner_addr})
    if receipt == "external":
        dest_set = dest_set.union({"slot:audit"})
    if receipt == "partner":
        dest_set = dest_set.union({partner_addr})  # set union avoids duplicates

    # Get trusted data categories for this invocation
    data_categories = user_input.get("trusted_event_labels", [])
    data_set = set(data_categories)  # convert to set for subset checks

    # Policy restrictions: which categories are allowed in each slot
    policy = {
        "slot:audit": ["PAYMENT", "SECRET"],
        "slot:control": ["UNVERIFIED"],
        "slot:customer": ["SECRET", "UNVERIFIED"],
        "slot:public": ["PII", "PAYMENT", "SECRET"],
        "slot:vendor": ["PII", "SECRET"]
    }

    # Check if any destination slot would receive disallowed data categories
    # Using any() with a generator expression to avoid explicit loops
    violation = any(
        (slot in policy) and not data_set.issubset(set(policy[slot]))
        for slot in dest_set
    )

    return violation