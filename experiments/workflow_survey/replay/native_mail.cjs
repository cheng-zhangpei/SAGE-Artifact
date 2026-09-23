// Offline replay of audited upstream code blocks and Gmail MIME helpers.
// No HTTP client, credentials, SMTP transport, or n8n server is instantiated.
const fs = require('fs');
const vm = require('vm');
const ts = require('typescript');
const MailComposer = require('nodemailer/lib/mail-composer');
const p = JSON.parse(fs.readFileSync(0, 'utf8'));
const workflow = JSON.parse(fs.readFileSync(p.workflow_path, 'utf8')).workflow.workflow;
const helpersSource = fs.readFileSync(p.helper_path, 'utf8');
const parsed = ts.createSourceFile('helpers.ts', helpersSource, ts.ScriptTarget.Latest, true);
const needed = new Set(['prepareEmailAttachments', 'encodeEmail']);
const functions = parsed.statements.filter(s => ts.isFunctionDeclaration(s) && s.name && needed.has(s.name.text));
if (functions.length !== needed.size) throw new Error('Audited helper functions missing');
const js = ts.transpileModule(functions.map(s => s.getText(parsed)).join('\n'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}
}).outputText;
const scope = {exports:{}, Buffer, MailComposer, isEmpty:x=>!x || Object.keys(x).length===0,
  NodeOperationError:class extends Error{}, console};
vm.runInNewContext(js, scope, {timeout:5000});
function codeNode(name, values) {
  const code = workflow.nodes.find(n=>n.name===name)?.parameters?.jsCode;
  if (!code) throw new Error('Missing audited code node: '+name);
  // Only these two previously inspected source blocks are executed.
  return vm.runInNewContext('(function($,$input){'+code+'})', {}, {timeout:5000})(
    name=>({item:{json:values[name]}}), {first:()=>values.input});
}
(async()=>{
  const values = {
    'Set Context':{subject_prefix:'[Forward]',footer_note:'Offline study fixture'},
    'Zoho Mail Trigger':{subject:'Document',fromAddress:'sender@example.invalid',toAddress:'owner@example.invalid',
      receivedTime:'2026-09-08T00:00:00Z',summary:'Please find the document attached.',html:'Please find the document attached.'},
    'AI Agent':{output:{type:'Notification',priority:'Low',summary:'A document is attached.',key_numbers:[]}}
  };
  const built=codeNode('Build Email HTML', values)[0].json;
  const payload=Buffer.from(p.content_base64,'base64');
  const binary={data:{fileName:'document.bin',mimeType:'application/octet-stream',data:p.content_base64}};
  const list=codeNode('Build Attachment List',{input:{json:{},binary}})[0];
  const q={to:'recipient@example.invalid',subject:built.emailSubject,body:built.emailHtml,attachmentFields:list.json.attachmentNames};
  if(p.deny) {process.stdout.write(JSON.stringify({request:q,denied:true,mime_base64:null})); return;}
  const ctx={helpers:{assertBinaryData:(_i,key)=>list.binary[key],
    getBinaryDataBuffer:async(_i,key)=>Buffer.from(list.binary[key].data,'base64')}, getNode:()=>({name:'offline-gmail'})};
  const attachments=await scope.exports.prepareEmailAttachments.call(ctx,{attachmentsBinary:[{property:q.attachmentFields}]},0);
  const raw=await scope.exports.encodeEmail({from:'owner@example.invalid',to:q.to,subject:q.subject,htmlBody:q.body,attachments});
  process.stdout.write(JSON.stringify({request:q,denied:false,mime_base64:raw,attachment_count:attachments.length}));
})().catch(e=>{console.error(e.stack);process.exit(1)});
