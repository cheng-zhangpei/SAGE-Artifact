import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    agent = user_input.get("agent")
    tool = user_input.get("tool")
    trusted_labels = user_input.get("trusted_event_labels", [])

    # Define the policy for destination slots
    policy = {
        "slot:audit": ["PAYMENT", "SECRET"],
        "slot:control": ["UNVERIFIED"],
        "slot:customer": ["SECRET", "UNVERIFIED"],
        "slot:public": ["PII", "PAYMENT", "SECRET"],
        "slot:vendor": ["PII", "SECRET"]
    }

    # For non-dispatch tools, they write to unrestricted slots (not in policy), so allow
    if tool != "dispatch":
        return False

    # Parse tool parameters for dispatch
    params = json.loads(tool_input)
    mode = params.get("mode")
    receipt = params.get("receipt")
    route = params.get("route")
    source = params.get("source")  # Not needed for destination slot calculation

    # Compute primary destination slot based on agent and route alias
    if agent == "support":
        route_map = {"local": "slot:internal", "partner": "slot:customer", "release": "slot:public"}
    elif agent == "finance":
        route_map = {"local": "slot:internal", "partner": "slot:vendor", "release": "slot:control"}
    else:
        # Unknown agent, stop the call to be safe
        return True

    primary_slot = route_map.get(route)
    if primary_slot is None:
        # Invalid route, stop the call
        return True

    # Collect all destination slots
    destination_slots = set([primary_slot])

    if mode == "mirror":
        destination_slots.add("slot:public")

    if mode == "linked":
        partner_slot = "slot:customer" if agent == "support" else "slot:vendor"
        destination_slots.add(partner_slot)

    if receipt == "external":
        destination_slots.add("slot:audit")

    if receipt == "partner":
        partner_slot = "slot:customer" if agent == "support" else "slot:vendor"
        if route != "partner":
            destination_slots.add(partner_slot)

    # Check each destination slot against policy
    for slot in destination_slots:
        if slot in policy:
            allowed_labels = set(policy[slot])
            if not set(trusted_labels).issubset(allowed_labels):
                # Violation: data labels not allowed in this slot
                return True

    # All checks passed, allow the call
    return False