import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool_input
    params = json.loads(tool_input) if isinstance(tool_input, str) else tool_input
    tool_name = user_input.get("tool", "")
    agent = user_input.get("agent", "")

    # Policy dictionary from the problem statement
    policy = {
        "slot:assessor": ["PRICING", "ACCESS"],
        "slot:escrow": ["ACCESS", "UNSCREENED"],
        "slot:oversight": ["UNSCREENED"],
        "slot:public": ["CUSTOMER", "PRICING", "ACCESS"],
        "slot:supplier": ["CUSTOMER", "ACCESS"]
    }
    all_labels = {"ACCESS", "CUSTOMER", "PRICING", "UNSCREENED"}

    # For non-transfer tools, allow unconditionally
    if tool_name != "transfer_case":
        return False

    # For transfer_case, compute possible labels in the content
    source = params.get("source", "")
    enclosure = params.get("enclosure", "none")
    possible_labels = set()

    # If source is not onboarding_guide, it could contain any sensitive label
    if source != "onboarding_guide":
        possible_labels.update(all_labels)
    # If enclosure attaches case or package, they could contain any sensitive label
    if enclosure == "case" or enclosure == "package":
        possible_labels.update(all_labels)

    # If no possible sensitive labels, always safe
    if not possible_labels:
        return False

    # Determine destination slots
    recipient = params.get("recipient", "")
    replica = params.get("replica", "none")
    destinations = set()

    # Primary recipient slot mapping
    if agent == "procurement":
        if recipient == "local":
            destinations.add("slot:operations")
        elif recipient == "partner":
            destinations.add("slot:supplier")
        elif recipient == "oversight":
            destinations.add("slot:public")
    elif agent == "compliance":
        if recipient == "local":
            destinations.add("slot:operations")
        elif recipient == "partner":
            destinations.add("slot:assessor")
        elif recipient == "oversight":
            destinations.add("slot:oversight")

    # Replica slots
    if replica == "public":
        destinations.add("slot:public")
    elif replica == "escrow":
        destinations.add("slot:escrow")
    elif replica == "partner":
        if agent == "procurement":
            destinations.add("slot:supplier")
        elif agent == "compliance":
            destinations.add("slot:assessor")

    # Check each destination slot against policy
    for slot in destinations:
        forbidden = policy.get(slot, [])
        if any(label in forbidden for label in possible_labels):
            return True

    return False