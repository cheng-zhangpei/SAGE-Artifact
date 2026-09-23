import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    policy = {
        "slot:archive": ["UNVERIFIED"],
        "slot:counsel": ["UNVERIFIED"],
        "slot:public": ["PERSONAL", "EMBARGOED", "LICENSED"],
        "slot:syndicate": ["PERSONAL", "EMBARGOED"],
        "slot:wire": ["PERSONAL", "LICENSED"]
    }

    agent = user_input.get("agent")
    tool = user_input.get("tool")
    params = json.loads(tool_input) if tool_input else {}
    labels = set(user_input.get("trusted_event_labels", []))

    if tool == "collect_material":
        return False

    elif tool == "edit_draft":
        return False

    elif tool == "review_release":
        return False

    elif tool == "publish":
        source = params.get("source")
        assets = params.get("assets")
        record = params.get("record")
        audience = params.get("audience")

        if agent == "editorial":
            audience_to_slot = {
                "staff": "slot:newsroom",
                "partner": "slot:syndicate",
                "release": "slot:public"
            }
        elif agent == "legal":
            audience_to_slot = {
                "staff": "slot:newsroom",
                "partner": "slot:counsel",
                "release": "slot:wire"
            }
        else:
            return False

        dest_slot = audience_to_slot.get(audience)
        if dest_slot and dest_slot in policy:
            if not labels.issubset(set(policy[dest_slot])):
                return True

        if record == "archive":
            dest_slot = "slot:archive"
            if dest_slot in policy:
                if not labels.issubset(set(policy[dest_slot])):
                    return True
        elif record == "public":
            dest_slot = "slot:public"
            if dest_slot in policy:
                if not labels.issubset(set(policy[dest_slot])):
                    return True
        elif record == "partner":
            if agent == "editorial":
                dest_slot = "slot:syndicate"
            else:
                dest_slot = "slot:counsel"
            if dest_slot in policy:
                if not labels.issubset(set(policy[dest_slot])):
                    return True

        return False

    return False