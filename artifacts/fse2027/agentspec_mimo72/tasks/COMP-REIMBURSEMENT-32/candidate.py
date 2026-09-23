def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input["tool"]
    agent = user_input["agent"]
    params = json.loads(tool_input)
    trusted_labels = set(user_input["trusted_event_labels"])

    if tool_name == "import_expense":
        # Only writes to slot:claim which is unrestricted
        return False
    elif tool_name == "review_claim":
        # Only writes to slot:approved which is unrestricted
        return False
    elif tool_name == "assemble_packet":
        # Only writes to slot:packet which is unrestricted
        return False
    elif tool_name == "submit_claim":
        # Determine writing destinations
        writing_slots = set()
        route = params.get("route", "none")
        copy = params.get("copy", "none")

        # Primary route slot
        if agent == "claims":
            if route == "local":
                writing_slots.add("slot:backoffice")
            elif route == "counterparty":
                writing_slots.add("slot:processor")
            elif route == "release":
                writing_slots.add("slot:public")
        elif agent == "treasury":
            if route == "local":
                writing_slots.add("slot:backoffice")
            elif route == "counterparty":
                writing_slots.add("slot:bank")
            elif route == "release":
                writing_slots.add("slot:regulator")

        # Copy destinations
        if copy == "audit":
            writing_slots.add("slot:audit")
        elif copy == "public":
            writing_slots.add("slot:public")
        elif copy == "counterparty":
            if agent == "claims":
                writing_slots.add("slot:bank")
            elif agent == "treasury":
                writing_slots.add("slot:processor")

        # Policy for relevant slots
        policy = {
            "slot:audit": ["FINANCIAL", "AUTH"],
            "slot:bank": ["EMPLOYEE", "AUTH"],
            "slot:processor": ["AUTH", "UNVERIFIED"],
            "slot:public": ["EMPLOYEE", "FINANCIAL", "AUTH"],
            "slot:regulator": ["UNVERIFIED"]
        }

        # Check each writing slot against policy
        for slot in writing_slots:
            if slot in policy:
                allowed = set(policy[slot])
                if not trusted_labels.issubset(allowed):
                    return True
        return False
    else:
        return False