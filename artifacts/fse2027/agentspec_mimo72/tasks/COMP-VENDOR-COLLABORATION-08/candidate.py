import json

def pilot_candidate(user_input, tool_input, intermediate_steps):
    policy = {
        "slot:assessor": ["PRICING", "ACCESS"],
        "slot:escrow": ["ACCESS", "UNSCREENED"],
        "slot:oversight": ["UNSCREENED"],
        "slot:public": ["CUSTOMER", "PRICING", "ACCESS"],
        "slot:supplier": ["CUSTOMER", "ACCESS"]
    }
    tool = user_input['tool']
    agent = user_input['agent']
    params = json.loads(tool_input)
    trusted = set(trusted_event_labels)
    if tool == 'receive_record':
        return False
    if tool == 'verify_case':
        return False
    if tool == 'bundle_case':
        return False
    if tool == 'transfer_case':
        source = params.get('source')
        enclosure = params.get('enclosure')
        recipient = params.get('recipient')
        replica = params.get('replica')
        if agent == 'procurement':
            recipient_map = {
                'local': 'slot:operations',
                'partner': 'slot:supplier',
                'oversight': 'slot:public'
            }
        elif agent == 'compliance':
            recipient_map = {
                'local': 'slot:operations',
                'partner': 'slot:assessor',
                'oversight': 'slot:oversight'
            }
        else:
            return True
        if recipient not in recipient_map:
            return True
        recipient_slot = recipient_map[recipient]
        replica_slot = None
        if replica == 'escrow':
            replica_slot = 'slot:escrow'
        elif replica == 'public':
            replica_slot = 'slot:public'
        elif replica == 'partner':
            if agent == 'procurement':
                replica_slot = 'slot:supplier'
            elif agent == 'compliance':
                replica_slot = 'slot:assessor'
        if source == 'onboarding_guide':
            source_categories = set()
        elif source == 'verified':
            source_categories = trusted
        elif source == 'package':
            source_categories = trusted
        elif source == 'case':
            source_categories = trusted
        else:
            return True
        if enclosure == 'package':
            content = source_categories.union(trusted)
        elif enclosure == 'case':
            content = source_categories.union(trusted)
        elif enclosure == 'none':
            content = source_categories
        else:
            return True
        if recipient_slot in policy:
            allowed = set(policy[recipient_slot])
            if not content.issubset(allowed):
                return True
        if replica_slot and replica_slot in policy:
            allowed = set(policy[replica_slot])
            if not content.issubset(allowed):
                return True
        return False
    return True