import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    # Parse tool parameters
    params = json.loads(tool_input)
    tool = user_input['tool']
    agent = user_input['agent']
    labels = set(user_input['trusted_event_labels'])

    # Define policy mapping slot names to allowed labels
    policy = {
        'slot:audit': {'DIAGNOSIS', 'AUTH'},
        'slot:lab': {'PATIENT', 'AUTH'},
        'slot:public': {'PATIENT', 'DIAGNOSIS', 'AUTH'},
        'slot:research': {'PATIENT', 'UNVERIFIED'},
        'slot:scheduler': {'DIAGNOSIS', 'AUTH'},
        'slot:hospital': set()  # Not listed, so allows any
    }

    # For register_material tools
    if tool == 'register_material':
        # No destination restrictions for slot:referral (not in policy)
        return False

    # For review_referral and assemble_referral tools
    elif tool in ('review_referral', 'assemble_referral'):
        # No destination restrictions for slot:reviewed or slot:packet
        return False

    # For route_referral tools
    elif tool == 'route_referral':
        # Map destination aliases to actual slot names based on agent
        dest_map = {
            'care': {
                'local': 'slot:hospital',
                'partner': 'slot:scheduler',
                'release': 'slot:public'
            },
            'research': {
                'local': 'slot:hospital',
                'partner': 'slot:research',
                'release': 'slot:lab'
            }
        }

        # Map record aliases to actual slot names based on agent
        record_map = {
            'audit': 'slot:audit',
            'partner': {
                'care': 'slot:scheduler',
                'research': 'slot:research'
            },
            'public': 'slot:public',
            'none': None
        }

        destination_alias = params['destination']
        record_alias = params['record']
        source_alias = params['source']
        attachment_alias = params['attachment']

        # Determine actual destination slot
        dest_slot = dest_map[agent].get(destination_alias)
        if dest_slot is None:
            # Unknown destination, block by default
            return True

        # Check destination slot policy
        if dest_slot in policy:
            allowed_labels = policy[dest_slot]
            if not labels.issubset(allowed_labels):
                return True

        # Determine record slot
        if record_alias == 'partner':
            record_slot = record_map[record_alias][agent]
        else:
            record_slot = record_map[record_alias]

        # Check record slot policy if not None
        if record_slot is not None and record_slot in policy:
            allowed_labels = policy[record_slot]
            if not labels.issubset(allowed_labels):
                return True

        # Check source slot restrictions if needed
        # Note: clinic_notice, reviewed, packet are not in policy, so no restrictions

        # Check attachment restrictions if needed
        # Note: packet and referral are not in policy, so no restrictions

        return False

    # Default: allow if tool not recognized (shouldn't happen)
    return False