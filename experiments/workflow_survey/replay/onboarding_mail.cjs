// Controlled boundary replay: original Gmail helpers, resolved original expressions.
// No network or SMTP transport. This is not execution of the complete n8n graph.
const fs=require('fs'),vm=require('vm'),ts=require('typescript');
const MailComposer=require('nodemailer/lib/mail-composer');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const w=JSON.parse(fs.readFileSync(p.workflow_path,'utf8')).workflow.workflow;
const source=fs.readFileSync(p.helper_path,'utf8');
const ast=ts.createSourceFile('helpers.ts',source,ts.ScriptTarget.Latest,true);
const wanted=new Set(['prepareEmailAttachments','encodeEmail']);
const fun=ast.statements.filter(s=>ts.isFunctionDeclaration(s)&&s.name&&wanted.has(s.name.text));
if(fun.length!==2)throw Error('Upstream helpers changed');
const js=ts.transpileModule(fun.map(s=>s.getText(ast)).join('\n'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const scope={exports:{},Buffer,MailComposer,isEmpty:x=>!x||Object.keys(x).length===0,NodeOperationError:class extends Error{}};
vm.runInNewContext(js,scope,{timeout:5000});
const n=w.nodes.find(n=>n.name===p.node_name);
if(!n||n.type!=='n8n-nodes-base.gmail')throw Error('Wrong source node');
const resolve=value=>{
  const m=/^=\{\{ \$json\.data\[0\]\.output\.([a-z_]+) \}\}$/.exec(value);
  if(m){if(!(m[1] in p.ai_output))throw Error('Missing fixture output');return p.ai_output[m[1]];}
  if(value==="={{ $('Onboarding Form').item.json['Email Address'] }}")return 'new-hire@example.invalid';
  if(value.startsWith('='))throw Error('Unsupported expression');
  return value;
};
const q={to:resolve(n.parameters.sendTo),subject:resolve(n.parameters.subject),body:resolve(n.parameters.message),options:n.parameters.options};
const binaries={data:Buffer.from(p.document_base64,'base64'),data_1:Buffer.from('PUBLIC POLICY FIXTURE\n')};
(async()=>{
  let attachments=[];const reads=[];
  if(p.deny){process.stdout.write(JSON.stringify({request:q,reads,mime_base64:null}));return;}
  if(q.options.attachmentsUi){
    // Apply property default documented in pinned MessageDescription.ts.
    const options={attachmentsBinary:q.options.attachmentsUi.attachmentsBinary.map(x=>({property:x.property??'data'}))};
    const context={getNode:()=>n,helpers:{assertBinaryData:(_i,k)=>{if(!binaries[k])throw Error('Missing binary '+k);return {fileName:k+'.txt',mimeType:'text/plain'};},getBinaryDataBuffer:async(_i,k)=>{reads.push(k);return binaries[k];}}};
    attachments=await scope.exports.prepareEmailAttachments.call(context,options,0);
  }
  const raw=await scope.exports.encodeEmail({from:'study@example.invalid',to:q.to,subject:q.subject,htmlBody:q.body,attachments});
  process.stdout.write(JSON.stringify({request:q,reads,mime_base64:raw}));
})().catch(e=>{process.stderr.write(e.stack);process.exit(1)});
