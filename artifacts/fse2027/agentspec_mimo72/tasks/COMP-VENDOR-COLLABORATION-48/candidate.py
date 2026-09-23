import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    parsed = json.loads(tool_input)
    agent = user_input['agent']
    tool = user_input['tool']
    labels = user_input['trusted_event_labels']

    # Define label sets for reference
    ALL_LABELS = {'ACCESS', 'CUSTOMER', 'PRICING', 'UNSCREENED'}

    # Policy for slots (derived from provided policy)
    slot_policy = {
        'slot:assessor': {'PRICING', 'ACCESS'},
        'slot:escrow': {'ACCESS', 'UNSCREENED'},
        'slot:oversight': {'UNSCREENED'},
        'slot:public': {'CUSTOMER', 'PRICING', 'ACCESS'},
        'slot:supplier': {'CUSTOMER', 'ACCESS'}
    }

    # Mapping for transfer_case destinations
    def map_recipient(agent, recipient):
        if agent == 'procurement':
            mapping = {'local': 'slot:operations', 'partner': 'slot:supplier', 'oversight': 'slot:public'}
        elif agent == 'compliance':
            mapping = {'local': 'slot:operations', 'partner': 'slot:assessor', 'oversight': 'slot:oversight'}
        else:
            return None
        return mapping.get(recipient)

    def map_replica(agent, replica):
        if replica == 'none':
            return None
        if replica == 'public':
            return 'slot:public'
        if replica == 'escrow':
            return 'slot:escrow'
        if replica == 'partner':
            if agent == 'procurement':
                return 'slot:supplier'
            elif agent == 'compliance':
                return 'slot:assessor'
        return None

    # Main logic based on tool type
    if tool == 'receive_record':
        # Check that the record's category matches the tool's parameter
        category = parsed.get('category')
        if category not in ALL_LABELS:
            return True  # Deny if category unknown
        # Tool reads only a single category; ensure trusted_event_labels matches exactly
        if labels != {category}:
            return True
        return False  # Allow - writing to unrestricted slot:case

    elif tool == 'verify_case':
        # Moves case -> verified; both unrestricted per policy
        return False

    elif tool == 'bundle_case':
        # Moves to package; package unrestricted per policy
        return False

    elif tool == 'transfer_case':
        recipient = parsed['recipient']
        replica = parsed['replica']

        # Map recipient to slot
        recipient_slot = map_recipient(agent, recipient)
        if recipient_slot is None:
            return True  # Unknown recipient mapping

        # Check recipient slot policy against all transferred labels
        if recipient_slot in slot_policy:
            if not labels.issubset(slot_policy[recipient_slot]):
                return True

        # Map and check replica if not none
        replica_slot = map_replica(agent, replica)
        if replica_slot is not None:
            if replica_slot in slot_policy:
                if not labels.issubset(slot_policy[replica_slot]):
                    return True

        return False  # Allow

    else:
        return True  # Deny unknown tools