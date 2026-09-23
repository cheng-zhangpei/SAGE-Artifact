"""SAGE synthesis/verification + offline native n8n function replay for pilot 13845."""
from __future__ import annotations
import argparse
import base64
from email import policy as email_policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sage.v2.model import Location, ToolModel, make_action, make_policy, make_state
from sage.v2.properties import compute_event_domain, observation_collisions, observation_ctx, observation_event
from sage.v2.synthesis import direct_sage
from sage.v2.guards import deny_constraints
from sage.v2.counterexample import shortest_counterexample as find_counterexample
from sage.v2.semantics import execute

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workflow',type=Path,required=True)
    p.add_argument('--helpers',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--node', default='node', help='Path to a Node.js executable')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    w=json.loads(args.workflow.read_text(encoding='utf-8'))['workflow']['workflow']
    names={n['name'] for n in w['nodes']}
    required={'AI Agent','Get Attachment Content','Build Attachment List','Forward Email with Attachments'}
    if not required <= names: raise ValueError('Wrong workflow fixture')
    ctx=Location.ctx('analyzer'); remote=Location.slot('remote_attachment'); binary=Location.slot('binary'); sink=Location.slot('mail')
    # The internal loaded marker models ordering, not confidentiality.
    fetch=make_action('backend','fetch',{'ref':'attachment'},[remote],[binary],['loaded'])
    send=make_action('analyzer','send',{'to':'recipient@example.invalid','field':'data'},[ctx,binary],[sink])
    actions=(fetch,send)
    model=ToolModel(frozenset({'backend','analyzer'}),frozenset({'fetch','send'}),
        frozenset({ctx,remote,binary,sink}),frozenset({'restricted','loaded'}),actions,
        enabled_fn=lambda x,u: ('loaded' not in x.get(binary)) if u==fetch else ('loaded' in x.get(binary)))
    policy=make_policy({sink:['restricted']})
    compiled=direct_sage(model,policy)
    E,D=set(),set()
    initials=[make_state({remote:labels}) for labels in ([],['restricted'])]
    for initial in initials:
        e,d=compute_event_domain(model,policy,initial,max_states=32)
        E.update(e);D.update(d)
        assert find_counterexample(model,policy,compiled,initial,max_states=32) is None
    collision_ctx=observation_collisions(observation_ctx,E,D)
    collision_event=observation_collisions(observation_event,E,D)
    bad_observations={observation_ctx(*e) for e in D}
    broken=find_counterexample(model,policy,(),initials[1],max_states=32)
    assert broken is not None and collision_ctx and not collision_event
    rows=[]; requests={}
    for mode in ('no_guard','ctx_safe','sage_direct'):
        for kind,content,initial in [('public',b'PUBLIC STUDY ATTACHMENT\n',initials[0]),
                                     ('restricted',b'RESTRICTED STUDY ATTACHMENT\n',initials[1])]:
            before=execute(initial,fetch)
            deny = (observation_ctx(before,send) in bad_observations) if mode=='ctx_safe' else (
                deny_constraints(compiled,before,send) if mode=='sage_direct' else False)
            command={'workflow_path':str(args.workflow.resolve()),'helper_path':str(args.helpers.resolve()),
                     'content_base64':base64.b64encode(content).decode(),'deny':deny}
            result=subprocess.run([args.node,str(Path(__file__).parent/'replay/native_mail.cjs')],
                input=json.dumps(command),capture_output=True,text=True,encoding='utf-8',timeout=30,check=True)
            native=json.loads(result.stdout); requests[(mode,kind)]=native['request']
            attachments=[]
            if native['mime_base64']:
                encoded=native['mime_base64']; raw=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4))
                message=BytesParser(policy=email_policy.default).parsebytes(raw)
                attachments=[a.get_payload(decode=True) for a in message.iter_attachments()]
                assert attachments==[content]
                (args.output/f'{mode}_{kind}.eml').write_bytes(raw)
            rows.append({'mode':mode,'fixture':kind,'denied':deny,'physical_attachment_count':len(attachments),
                         'restricted_bytes_emitted':kind=='restricted' and bool(attachments),
                         'public_forward_completed':kind=='public' and attachments==[content]})
    assert len({json.dumps(q,sort_keys=True) for q in requests.values()})==1
    report={'scope':'single external workflow; synthetic pair; native code/MIME helper replay; no n8n server, Zoho or Gmail execution',
            'workflow_sha256':hashlib.sha256(args.workflow.read_bytes()).hexdigest(),
            'helpers_sha256':hashlib.sha256(args.helpers.read_bytes()).hexdigest(),
            'helper_commit':'418f85e9ebf12a1485196e982f745b0e360c818d',
            'candidate_contract_status':'manually reviewed slice; abstract download; fixed neutral metadata and AI output; source labels and destination policy added by study',
            'model_event_count':len(E),'model_danger_count':len(D),
            'ctx_collision_classes':len(collision_ctx),'event_collision_classes':len(collision_event),
            'compiled_rules':[c.canonical() for c in compiled],
            'compiled_guard_verified_for_both_initials':True,
            'empty_guard_counterexample':[step.action.canonical() for step in broken.trace],
            'same_resolved_mail_request':True,'rows':rows,
            'negative_control_ctx_already_restricted':deny_constraints(compiled,make_state({ctx:['restricted'],binary:['loaded']}),send)}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
