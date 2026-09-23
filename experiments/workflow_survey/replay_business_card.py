"""SAGE collision check and native MIME-boundary replay for template 19292."""
import argparse,base64,hashlib,json,subprocess,sys
from email import policy as ep
from email.parser import BytesParser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sage.v2.model import Location,ToolModel,make_action,make_policy,make_state
from sage.v2.properties import compute_event_domain,observation_collisions,observation_ctx,observation_event
from sage.v2.synthesis import direct_sage
from sage.v2.guards import deny_constraints
from sage.v2.counterexample import shortest_counterexample
from sage.v2.semantics import execute

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--helpers',type=Path,required=True);p.add_argument('--node',default='node');a=p.parse_args()
 workflow=a.root/'workflows/19292.json';out=a.root/'pilot_19292';out.mkdir(exist_ok=True)
 doc=json.loads(workflow.read_bytes())['workflow']['workflow'];names={n['name'] for n in doc['nodes']}
 assert {'Extract Card Data with Gemini','Download Attachment from Drive','Create Draft with Attachment'}<=names
 ctx=Location.ctx('card_agent');remote=Location.slot('configured_drive_attachment');binary=Location.slot('attachment');sink=Location.slot('gmail_draft')
 fetch=make_action('backend','download_attachment',{'file_id':'fixed_study_id'},[remote],[binary],['loaded'])
 send=make_action('card_agent','create_draft',{'to':'contact@example.invalid','attachment':'attachment'},[ctx,binary],[sink])
 model=ToolModel(frozenset({'backend','card_agent'}),frozenset({'download_attachment','create_draft'}),frozenset({ctx,remote,binary,sink}),frozenset({'restricted','loaded'}),(fetch,send),enabled_fn=lambda s,u:'loaded' not in s.get(binary) if u==fetch else 'loaded' in s.get(binary))
 policy=make_policy({sink:['restricted']});guard=direct_sage(model,policy);initials=[make_state({remote:x}) for x in ([],['restricted'])]
 E=set();D=set()
 for initial in initials:
  e,d=compute_event_domain(model,policy,initial,max_states=32);E|=e;D|=d
  assert shortest_counterexample(model,policy,guard,initial,max_states=32) is None
 ctxc=observation_collisions(observation_ctx,E,D);eventc=observation_collisions(observation_event,E,D)
 assert len(ctxc)==1 and not eventc
 badctx={observation_ctx(*e) for e in D};rows=[];requests=[]
 for mode in ('ctx_safe','sage_direct'):
  for kind,content,initial in [('public',b'%PDF-PUBLIC STUDY OVERVIEW\n',initials[0]),('restricted',b'%PDF-RESTRICTED STUDY OVERVIEW\n',initials[1])]:
   state=execute(initial,fetch);deny=observation_ctx(state,send) in badctx if mode=='ctx_safe' else deny_constraints(guard,state,send)
   command={'workflow_path':str(workflow),'helper_path':str(a.helpers),'content_base64':base64.b64encode(content).decode(),'deny':deny}
   result=subprocess.run([a.node,str(Path(__file__).parent/'replay/business_card_mail.cjs')],input=json.dumps(command),text=True,encoding='utf-8',capture_output=True,timeout=30,check=True)
   native=json.loads(result.stdout);requests.append(native['request']);attachments=[]
   if native['mime_base64']:
    b=native['mime_base64'];raw=base64.urlsafe_b64decode(b+'='*(-len(b)%4));mail=BytesParser(policy=ep.default).parsebytes(raw);attachments=[x.get_payload(decode=True) for x in mail.iter_attachments()];assert attachments==[content];(out/f'{mode}_{kind}.eml').write_bytes(raw)
   rows.append({'mode':mode,'fixture':kind,'denied':deny,'attachment_count':len(attachments),'restricted_bytes_emitted':kind=='restricted' and bool(attachments),'public_completed':kind=='public' and attachments==[content]})
 assert len({json.dumps(q,sort_keys=True) for q in requests})==1
 report={'scope':'one external public template; two synthetic resource-label fixtures; original Gmail MIME helpers; no full n8n/Drive/Gmail execution',
  'workflow_sha256':hashlib.sha256(workflow.read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(a.helpers.read_bytes()).hexdigest(),
  'source_evidence':'AI reads the business-card image; a separately configured Drive attachment is downloaded after body/recipient construction and selected by the original Gmail draft node.',
  'study_inputs':'fixed configured file ID, business card, recipient and request; resource confidentiality label and destination policy vary by fixture.',
  'ctx_collision_classes':len(ctxc),'event_collision_classes':len(eventc),'compiled_verified':True,'same_resolved_draft_request':True,'rows':rows,
  'limits':['Existence is relative to the reviewed contract, supplied labels/policy and finite slice.','Template attachment_file_id is an unset deployment placeholder.','No claim of native deployment prevalence or end-to-end workflow execution.']}
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
