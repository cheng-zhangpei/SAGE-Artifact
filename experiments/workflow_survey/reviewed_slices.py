"""SAGE checks on source-reviewed slices; contracts and policies are study inputs.

This does not translate arbitrary n8n JSON or certify full workflow execution.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sage.v2.model import Location, ToolModel, make_action, make_policy, make_state
from sage.v2.properties import compute_event_domain, observation_collisions, observation_ctx, observation_event
from sage.v2.synthesis import direct_sage
from sage.v2.counterexample import shortest_counterexample
from sage.v2.guards import deny_constraints
from sage.v2.semantics import deny_star
from attribute_denials import attribute

LEGACY_CASES = [
    dict(id=6531, kind='independent_binary', sources=['Image Style'], sink='Save Image',
         required=['LinkedIn Creator Agent','Image Style','OpenAI Image1','Convert to File','Save Image'],
         rationale='The image generator receives an independently downloaded Drive reference image plus the AI-produced prompt; the earlier agent does not read the reference bytes.',
         limitations='Collapsed image-generation transformation; study labels and Drive destination policy. The generated output conservatively inherits reference-image provenance.'),
    dict(id=8104, kind='independent_binary', sources=['Google Drive'], sink='Gmail',
         required=['Google Drive','Google Drive1','OpenAI','OpenAI1','Google Docs','Google Drive2','Gmail'],
         rationale='A fixed Google Docs proposal template is copied, filled with AI-generated text, exported, and attached to a prospect email. The AI reads the call transcript, not the template resource.',
         limitations='Collapsed Docs copy/update/export chain; study varies template label while fixing template ID, prospect and generated fields. Gmail creates a draft; no live service execution.'),
    dict(id=10126, kind='independent_binary', sources=['Generate Thumbnail via Templated.io'], sink='Upload to Google Drive',
         required=['OpenAI Post Generation1','Generate Thumbnail via Templated.io','Download Thumbnail','Downloading files','Upload to Google Drive'],
         rationale='Templated.io combines a fixed external template with AI-produced layer text; the rendered binary is later downloaded and uploaded. Earlier AI does not read the template resource.',
         limitations='Remote template/render contracts are unavailable; output conservatively inherits template provenance. Study labels and Drive policy; no native execution.'),
    dict(id=13845, kind='independent_binary', sources=['Get Attachment Content'], sink='Forward Email with Attachments',
         required=['AI Agent','Get Attachment Content','Build Attachment List','Forward Email with Attachments'],
         rationale='AI reads message metadata/summary before attachment content is downloaded; original code passes the later binary field to Gmail.',
         limitations='Study labels and destination policy; abstracted trigger/download. Native code/MIME helper replay is reported separately.'),
    dict(id=11529, kind='independent_binary', sources=['Get Email Attachments'], sink='Save Photos to Drive',
         required=['Extract Email Info','Get Email Attachments','Filter Photos Only','Save Photos to Drive'],
         rationale='Extractor reads email text, then Gmail fetches attachments; filter reads MIME metadata. Fixed image metadata, varying photo labels; destination restriction supplied by study.',
         limitations='Gmail get body/attachment contract split needs trusted confirmation. Calendar and reminder branches excluded. Original expression defects not repaired or executed.'),
    dict(id=15449, kind='independent_binary', sources=['Download Handbook','Download Policy'], sink='Welcome Email → New Hire',
         required=['AI Agent','Download Handbook','Download Policy','Merge','Aggregate','Welcome Email → New Hire'],
         rationale='AI prompt reads form fields; handbook and policy downloaded later, aggregated with binaries and attached. Vary document confidentiality relative to new-hire destination, keep form/AI result fixed.',
         limitations='Credentials and document IDs are placeholders. Merge/binary naming needs native runtime validation. Study label is restricted-to-recipient, not generic employee PII.'),
    dict(id=15451, kind='independent_binary', sources=['Download Handbook','Download Policy'], sink='Welcome Email → New Hire',
         required=['AI Agent','Download Handbook','Download Policy','Merge','Aggregate','Welcome Email → New Hire'],
         rationale='Same onboarding structure as 15449; retain as near-duplicate, not independent supporting application.',
         limitations='Same author/template family must not be counted as two independent applications; no live execution.'),
    dict(id=19292, kind='independent_binary', sources=['Download Attachment from Drive'], sink='Create Draft with Attachment',
         required=['Extract Card Data with Gemini','Build Email Content','Download Attachment from Drive','Create Draft with Attachment'],
         rationale='Gemini reads a business-card image. A separately configured Drive file is downloaded only after the recipient/body are built and is explicitly attached to the Gmail draft.',
         limitations='The attachment_file_id is a deployment placeholder. Study varies its resource label while fixing the resolved ID, business card and recipient; draft creation is not live-executed.'),
    dict(id=11912, kind='generated_from_ctx', sources=['Get a message1'], sink='Upload file1',
         required=['Message a model2','Get a message1','Extract from File1','Message a model3','Upload file1'],
         rationale='Negative case: downstream resume-analysis AI explicitly reads text extracted from binary data0, so attachment provenance reaches AI context before later actions.',
         limitations='Abstract extraction and Drive upload; confirms why graph order alone overstates independent-resource paths.'),
    dict(id=13237, kind='generated_from_ctx', sources=['Get Attachment'], sink='Forward to freee',
         required=['Extract Text from PDF','Classify Invoice/Receipt (AI)','Get Attachment','Forward to freee'],
         rationale='Negative case: classifier prompt explicitly includes extracted attachment content before the same message attachment is refetched and forwarded.',
         limitations='Assumes trigger and refetch refer to the same immutable message; destination policy is study supplied.'),
    dict(id=15440, kind='generated_from_ctx', sources=['18. HTTP — Download Clip File'], sink='19. Google Drive — Upload Clip',
         required=['15. AI Agent — Write Platform Captions','18. HTTP — Download Clip File','19. Google Drive — Upload Clip'],
         rationale='Negative conservative case: AI captions read clip description, video summary and timestamps derived from the same upstream video/clip, so source provenance is retained in context.',
         limitations='WayinVideo contracts are remote and unavailable; this conservative contract may overtaint compared with a validated field-level model.'),
    dict(id=18142, kind='generated_from_ctx', sources=['Fetch Actual Image'], sink='Download Image',
         required=['AI Image Selector','Fetch Url','Fetch Actual Image','Download Image'],
         rationale='Negative case: the AI image selector analyzes the candidate image URLs before its selected large image is fetched and uploaded.',
         limitations='Pexels medium/large variants and HTTP bytes abstracted; a finer model would need their resource-identity contract.'),
    dict(id=7201, kind='generated_from_ctx', sources=['Google Drive-get_file'], sink='Gmail',
         required=['Basic LLM Chain-offerLetter','Convert to File','Google Drive-upload','Google Drive-get_file','Gmail'],
         rationale='Downloaded offer is generated from preceding LLM text. Preserve provenance through upload/download; do not invent an independently restricted replacement.',
         limitations='Assumes stored generated artifact is unchanged; external replacement would define a different scenario.'),
    dict(id=7695, kind='generated_from_ctx', sources=['Download file'], sink='Send Email',
         required=['AI Agent','Format Slides Data',' Build Presentation','Download file','Send Email'],
         rationale='Downloaded slides contain AI output derived from advertising metrics. Context already carries source label under union-flow.',
         limitations='API credentials/remote generation abstracted; no full workflow execution.'),
]

def load_cases(manifest_path):
    if manifest_path is None:
        return LEGACY_CASES
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    cases=[]
    for item in manifest['candidates']:
        spec=item.get('sage_model')
        if not spec:
            continue
        cases.append(dict(
            id=item['id'], kind=spec['kind'], sources=spec['sources'], sink=spec['sink'],
            required=spec['required_nodes'], rationale=item['review_evidence'],
            limitations=f"{item['policy_scope']}; {item['runtime_claim']}",
            candidate_status=item['final_status'], candidate_subtype=item.get('subtype'),
        ))
    return cases

def run(case, root):
    path=root/'workflows'/f"{case['id']}.json"
    raw=path.read_bytes(); doc=json.loads(raw)['workflow']; nodes={n['name']:n for n in doc['workflow']['nodes']}
    assert set(case['required']) <= set(nodes), 'Source changed: required nodes absent'
    ctx=Location.ctx('workflow_agent'); out=Location.slot('destination'); pc=Location.slot('control')
    remotes=[Location.slot(f'remote_{i}') for i in range(len(case['sources']))]
    binaries=[Location.slot(f'binary_{i}') for i in range(len(remotes))]
    actions=[]
    for i, name in enumerate(case['sources']):
        reads=[remotes[i]] if case['kind']=='independent_binary' else [ctx]
        actions.append(make_action('backend',name,{'resource':f'fixed_source_{i}'},reads,[binaries[i],pc],[f'step_{i+1}']))
    actions.append(make_action('workflow_agent',case['sink'],{'recipient':'study@example.invalid','binary_fields':','.join(str(i) for i in range(len(remotes)))},[ctx,*binaries],[out,pc],[f'step_{len(remotes)+1}']))
    def enabled(state, action):
        i=actions.index(action)
        return f'step_{i+1}' not in state.get(pc) and (i==0 or f'step_{i}' in state.get(pc))
    labels={'restricted',*(f'step_{i+1}' for i in range(len(actions)))}
    model=ToolModel(frozenset({'backend','workflow_agent'}),frozenset(a.tool for a in actions),
                    frozenset([ctx,out,pc,*remotes,*binaries]),frozenset(labels),tuple(actions),enabled_fn=enabled)
    policy=make_policy({out:['restricted']}); guard=direct_sage(model,policy)
    initials=[]
    if case['kind']=='independent_binary':
        for values in itertools.product([False,True],repeat=len(remotes)):
            initials.append(make_state({r:['restricted'] if v else [] for r,v in zip(remotes,values)}))
    else:
        initials=[make_state({ctx:ls}) for ls in ([],['restricted'])]
    E,D=set(),set(); counterexamples=[]
    for initial in initials:
        e,d=compute_event_domain(model,policy,initial,max_states=128);E.update(e);D.update(d)
        assert shortest_counterexample(model,policy,guard,initial,max_states=128) is None
        bad=shortest_counterexample(model,policy,(),initial,max_states=128)
        if bad: counterexamples.append([s.action.canonical() for s in bad.trace])
    results={}; attribution={}
    for name,obs in [('ctx',observation_ctx),('event',observation_event)]:
        collisions=observation_collisions(obs,E,D); dangerous_obs={obs(*e) for e in D}
        sends=[e for e in E if e[1]==actions[-1]]
        results[name]={'collision_classes':len(collisions),'benign_send_events':sum(e not in D for e in sends),
                       'blocked_benign_send_events':sum(e not in D and obs(*e) in dangerous_obs for e in sends)}
        attribution[name]=attribute(E,D,obs,lambda s,a:obs(s,a) in dangerous_obs,complete_domain=True)
    assert all(deny_constraints(guard,s,a)==deny_star(s,a,policy) for s,a in E)
    witnesses=[]
    for key in observation_collisions(observation_ctx,E,D):
        good=next(e for e in E-D if observation_ctx(*e)==key);bad=next(e for e in D if observation_ctx(*e)==key)
        witnesses.append({'same_action':good[1].canonical(),'benign_state':good[0].canonical(),'dangerous_state':bad[0].canonical()})
    return {**case,'source_sha256':hashlib.sha256(raw).hexdigest(),'source_name':doc['name'],
            'coverage':'exhaustive within declared finite sequential slice and listed initial states; not full n8n model',
            'policy_and_labels':'study supplied; no measured native attack/false-positive rate',
            'initial_state_count':len(initials),'events':len(E),'dangerous_events':len(D),
            'observations':results,'denial_attribution':attribution,'witnesses':witnesses,'compiled_rules':[c.canonical() for c in guard],
            'compiled_verified':True,'empty_guard_counterexamples':counterexamples,'native_execution':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path);args=p.parse_args()
    results=[run(c,args.root) for c in load_cases(args.manifest)]
    (args.root/'reviewed_slice_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'id':r['id'],'observations':r['observations'],'verified':r['compiled_verified']} for r in results]))

if __name__=='__main__':main()
