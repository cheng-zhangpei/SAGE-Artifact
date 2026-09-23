import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool_input to get parameters
    tool_params = json.loads(tool_input)

    # Extract agent, tool, and trusted labels from user_input
    tool_name = user_input.get("tool", "")
    agent_name = user_input.get("agent", "")
    labels = user_input.get("trusted_event_labels", [])

    # Policy dictionary from the workflow
    policy = {
        "slot:audit": ["SOURCE", "CREDENTIAL"],
        "slot:marketplace": ["CUSTOMER", "CREDENTIAL"],
        "slot:production": ["UNVERIFIED"],
        "slot:public": ["CUSTOMER", "SOURCE", "CREDENTIAL"],
        "slot:vendor": ["SOURCE", "CREDENTIAL"]
    }

    # Allow all tools except deliver_build (based on policy restrictions)
    if tool_name != "deliver_build":
        return False

    # For deliver_build, check channel and telemetry against policy
    channel = tool_params.get("channel")
    telemetry = tool_params.get("telemetry")

    # Determine main target slot based on agent and channel
    target_slot = None
    if agent_name == "release":
        if channel == "local":
            target_slot = "slot:internal"
        elif channel == "partner":
            target_slot = "slot:marketplace"
        elif channel == "release":
            target_slot = "slot:public"
    elif agent_name == "operations":
        if channel == "local":
            target_slot = "slot:internal"
        elif channel == "partner":
            target_slot = "slot:vendor"
        elif channel == "release":
            target_slot = "slot:production"

    # Determine telemetry slot (no policy restriction for partner)
    telemetry_slot = None
    if telemetry == "audit":
        telemetry_slot = "slot:audit"
    elif telemetry == "public":
        telemetry_slot = "slot:public"
    # partner telemetry maps to unlisted slot, so no check needed

    # Check if any label is disallowed in target_slot
    if target_slot is not None and target_slot in policy:
        disallowed = policy[target_slot]
        for label in labels:
            if label in disallowed:
                return True  # block the call

    # Check if any label is disallowed in telemetry_slot
    if telemetry_slot is not None and telemetry_slot in policy:
        disallowed = policy[telemetry_slot]
        for label in labels:
            if label in disallowed:
                return True  # block the call

    # If no violations, allow the call
    return False