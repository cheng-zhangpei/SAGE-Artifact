"""Attribute recorded decisions in a supplied SAGE event domain in one batch.

No model/labels are inferred here. Missing concrete oracle stays unknown.
"""
from collections import defaultdict

def attribute(events, dangers, observe, denied, concrete_allowed=None, complete_domain=False):
    events=set(events); dangers=set(dangers)
    if not dangers <= events:
        raise ValueError('Danger set must be a subset of the supplied event domain')
    by_obs=defaultdict(list)
    for e in dangers:
        by_obs[observe(*e)].append(e)
    rows=[]
    for e in sorted(events,key=lambda e:(e[0].canonical(),e[1].canonical())):
        if not denied(*e):
            continue
        mate=next(iter(by_obs.get(observe(*e),())),None)
        physical=concrete_allowed(e) if concrete_allowed else None
        if e in dangers:
            category='model_induced_blocking' if physical is True else ('correct_denial' if physical is False else 'model_danger_concrete_unknown')
        elif mate is not None:
            category='observation_collision'
        else:
            category='guard_extra_denial' if complete_domain else 'no_collision_found_domain_incomplete'
        rows.append({'state':e[0].canonical(),'action':e[1].canonical(),
                     'category':category,'concrete_allowed':physical,
                     'dangerous_mate':({'state':mate[0].canonical(),'action':mate[1].canonical()} if mate else None)})
    return rows
