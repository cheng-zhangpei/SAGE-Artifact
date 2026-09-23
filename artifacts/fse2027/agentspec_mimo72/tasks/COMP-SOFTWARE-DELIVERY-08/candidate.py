import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    tool_name = user_input['tool']
    agent = user_input['agent']
    trusted_labels = user_input.get('trusted_event_labels', [])
    params = json.loads(tool_input)

    # Policy definitions: slot -> allowed label set
    policy = {
        'slot:audit': ['SOURCE', 'CREDENTIAL'],
        'slot:marketplace': ['CUSTOMER', 'CREDENTIAL'],
        'slot:production': ['UNVERIFIED'],
        'slot:public': ['CUSTOMER', 'SOURCE', 'CREDENTIAL'],
        'slot:vendor': ['SOURCE', 'CREDENTIAL']
    }

    # Helper to check if labels are subset of allowed
    def is_allowed(target_slot, labels):
        if target_slot not in policy:
            return True  # unrestricted
        allowed = set(policy[target_slot])
        return set(labels).issubset(allowed)

    if tool_name == 'import_component':
        # Writes to slot:staging (unrestricted)
        return False

    elif tool_name == 'review_component':
        # Writes to slot:reviewed (unrestricted)
        return False

    elif tool_name == 'assemble_build':
        # Writes to slot:artifact (unrestricted)
        return False

    elif tool_name == 'deliver_build':
        channel = params.get('channel')
        payload = params.get('payload')
        source = params.get('source')
        telemetry = params.get('telemetry')

        # Determine destination slot based on agent and channel
        if agent == 'release':
            channel_map = {'local': 'slot:internal', 'partner': 'slot:marketplace', 'release': 'slot:public'}
        elif agent == 'operations':
            channel_map = {'local': 'slot:internal', 'partner': 'slot:vendor', 'release': 'slot:production'}
        else:
            # Unknown agent: block
            return True

        dest_slot = channel_map.get(channel)
        if not dest_slot:
            return True  # invalid channel

        # Determine labels that will be written
        # Base content from source
        if source == 'status_note':
            base_labels = set()
        elif source in ['reviewed', 'artifact']:
            # These slots contain whatever labels have been placed there
            # In a memoryless IFC, we only know current trusted_event_labels
            # Assume source contains the same trusted labels (conservative)
            base_labels = set(trusted_labels)
        else:
            return True  # invalid source

        # Add payload labels if not none
        if payload == 'artifact':
            # artifact slot contains whatever labels are in artifact
            payload_labels = set(trusted_labels)
            total_labels = base_labels.union(payload_labels)
        elif payload == 'staging':
            payload_labels = set(trusted_labels)
            total_labels = base_labels.union(payload_labels)
        elif payload == 'none':
            total_labels = base_labels
        else:
            return True  # invalid payload

        # Check primary destination
        if not is_allowed(dest_slot, total_labels):
            return True

        # Check telemetry destinations
        if telemetry == 'audit':
            if not is_allowed('slot:audit', total_labels):
                return True
        elif telemetry == 'partner':
            # partner destination is not restricted by policy
            pass
        elif telemetry == 'public':
            if not is_allowed('slot:public', total_labels):
                return True
        elif telemetry != 'none':
            return True  # invalid telemetry

        return False

    # Unknown tool: block by default
    return True