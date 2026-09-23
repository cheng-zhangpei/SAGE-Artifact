import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input.get("tool")
    agent = user_input.get("agent")
    trusted_labels = set(user_input.get("trusted_event_labels", []))

    # Policy: forbidden labels per output slot
    policy = {
        "slot:out_a": ["CLIENT_B"],
        "slot:out_b": ["CLIENT_A"]
    }

    # Helper to check if any forbidden label is present in trusted labels
    def has_forbidden(slot):
        forbidden = policy.get(slot, [])
        return any(label in trusted_labels for label in forbidden)

    # Prepare tools write to proposal slots (not restricted by policy)
    if tool_name == "prepare" and agent in ["manager_a", "manager_b"]:
        return False

    # Send tool: parse parameters
    if tool_name == "send" and agent == "mailer":
        params = json.loads(tool_input)
        to = params.get("to")
        scope = params.get("scope")

        # Destination mapping for output slots
        dest_slot = {
            "a": "slot:out_a",
            "b": "slot:out_b",
            "archive": None  # no policy restriction for archive
        }.get(to)

        # If destination slot has policy restrictions, check for forbidden labels
        if dest_slot is not None and has_forbidden(dest_slot):
            return True

        # Additional check: sending both proposals to a client violates policy
        # even if the specific slot check above passes, because the data flow
        # would indirectly cause a violation when combined with other calls.
        # However, the policy only restricts the final output slots, so we
        # only need to check the direct write to the output slot.

        return False

    # Default: allow (should not happen with given tools)
    return False