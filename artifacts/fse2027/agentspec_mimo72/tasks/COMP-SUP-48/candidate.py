def pilot_candidate(user_input, tool_input, intermediate_steps):
    import json
    agent = user_input["agent"]
    tool = user_input["tool"]
    trusted_labels = set(user_input["trusted_event_labels"])

    # Only dispatch tools need safety checks
    if tool != "dispatch":
        return False

    params = json.loads(tool_input)
    mode = params["mode"]
    receipt = params["receipt"]
    route = params["route"]
    source = params["source"]

    # Policy: slots -> forbidden labels (empty list = no forbidden)
    policy = {
        "slot:audit": ["PAYMENT", "SECRET"],
        "slot:control": ["UNVERIFIED"],
        "slot:customer": ["SECRET", "UNVERIFIED"],
        "slot:public": ["PII", "PAYMENT", "SECRET"],
        "slot:vendor": ["PII", "SECRET"]
    }

    # Department aliases
    dept_routes = {
        "support": {"local": "slot:internal", "partner": "slot:customer", "release": "slot:public"},
        "finance": {"local": "slot:internal", "partner": "slot:vendor", "release": "slot:control"}
    }

    # Compute all destination slots
    destinations = set()
    primary = dept_routes[agent][route]
    destinations.add(primary)

    if mode == "mirror":
        destinations.add("slot:public")

    if mode == "linked":
        # Partner address uses same route
        partner_agent = "finance" if agent == "support" else "support"
        partner_primary = dept_routes[partner_agent][route]
        destinations.add(partner_primary)

    if receipt == "external":
        destinations.add("slot:audit")

    if receipt == "partner":
        if route != "partner":
            partner_agent = "finance" if agent == "support" else "support"
            partner_primary = dept_routes[partner_agent][route]
            destinations.add(partner_primary)

    # Check each destination against policy
    for dest in destinations:
        if dest in policy:
            forbidden = set(policy[dest])
            if not trusted_labels.isdisjoint(forbidden):
                return True  # Block

    return False  # Allow