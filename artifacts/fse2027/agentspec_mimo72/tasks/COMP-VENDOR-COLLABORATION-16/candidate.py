import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    params = json.loads(tool_input)
    agent = user_input['agent']
    tool = user_input['tool']
    labels = set(user_input['trusted_event_labels'])

    if tool == 'receive_record':
        cat = params['category']
        # destination slot:case is unrestricted (not in policy)
        return False

    elif tool == 'verify_case':
        # destination slot:verified is unrestricted
        return False

    elif tool == 'bundle_case':
        # destination slot:package is unrestricted
        return False

    elif tool == 'transfer_case':
        recipient = params['recipient']
        replica = params['replica']
        # Map recipient to slot
        if agent == 'procurement':
            recipient_map = {'local': 'slot:operations', 'partner': 'slot:supplier', 'oversight': 'slot:public'}
        else:  # compliance
            recipient_map = {'local': 'slot:operations', 'partner': 'slot:assessor', 'oversight': 'slot:oversight'}
        dest = recipient_map.get(recipient)
        # Check policy for recipient slot
        policy = user_input.get('policy', {})
        if dest and dest in policy:
            allowed = set(policy[dest])
            if not labels.issubset(allowed):
                return True
        # Check replica slot if replica is not 'none'
        if replica != 'none':
            if replica == 'escrow':
                replica_slot = 'slot:escrow'
            elif replica == 'public':
                replica_slot = 'slot:public'
            elif replica == 'partner':
                if agent == 'procurement':
                    replica_slot = 'slot:supplier'
                else:
                    replica_slot = 'slot:assessor'
            else:
                replica_slot = None
            if replica_slot and replica_slot in policy:
                allowed = set(policy[replica_slot])
                if not labels.issubset(allowed):
                    return True
        return False

    # Default allow for any other tool (not expected)
    return False