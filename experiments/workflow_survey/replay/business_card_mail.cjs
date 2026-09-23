// Controlled replay of the original Gmail-draft boundary in n8n template 19292.
// No network, credentials, Gmail transport, or complete n8n engine is used.
const fs=require('fs'),vm=require('vm'),ts=require('typescript');
const MailComposer=require('nodemailer/lib/mail-composer');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
const w=JSON.parse(fs.readFileSync(p.workflow_path,'utf8')).workflow.workflow;
const helper=fs.readFileSync(p.helper_path,'utf8');
const ast=ts.createSourceFile('helpers.ts',helper,ts.ScriptTarget.Latest,true);
const wanted=new Set(['prepareEmailAttachments','encodeEmail']);
const funcs=ast.statements.filter(x=>ts.isFunctionDeclaration(x)&&x.name&&wanted.has(x.name.text));
if(funcs.length!==2)throw Error('Pinned helpers changed');
const js=ts.transpileModule(funcs.map(x=>x.getText(ast)).join('\n'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{},Buffer,MailComposer,isEmpty:x=>!x||Object.keys(x).length===0,NodeOperationError:class extends Error{}};
vm.runInNewContext(js,scope,{timeout:5000});
const node=w.nodes.find(x=>x.name==='Create Draft with Attachment');
if(!node)throw Error('Source node absent');
const card={company:'Example Co',department:'Research',title:'Engineer',name:'A. Person',email:'contact@example.invalid'};
const settings={sender_company:'SAGE Study',sender_name:'Researcher',sender_tel:'+0',sender_email:'study@example.invalid'};
const body=`${card.company}\n${card.department} ${card.title}\n${card.name}\n\nHello,\n\nThank you for taking the time to exchange business cards with us the other day.\nI am ${settings.sender_name} from ${settings.sender_company}.\n\n(Write your message here.)\n\nI have attached a short overview of what we do for your reference.\n\nKind regards,\n\n--------------------------------\n${settings.sender_company}\n${settings.sender_name}\nTEL: ${settings.sender_tel}\nMail: ${settings.sender_email}\n--------------------------------`;
const q={to:card.email,subject:`Thank you for the introduction - ${settings.sender_company}`,body,attachmentFields:['attachment']};
(async()=>{
 if(p.deny){process.stdout.write(JSON.stringify({request:q,denied:true,mime_base64:null,reads:[]}));return;}
 const payload=Buffer.from(p.content_base64,'base64'),reads=[];
 const ctx={getNode:()=>node,helpers:{assertBinaryData:(_i,k)=>({fileName:'overview.pdf',mimeType:'application/pdf'}),getBinaryDataBuffer:async(_i,k)=>{reads.push(k);return payload;}}};
 const attachments=await scope.exports.prepareEmailAttachments.call(ctx,{attachmentsBinary:[{property:'attachment'}]},0);
 const raw=await scope.exports.encodeEmail({from:settings.sender_email,to:q.to,subject:q.subject,htmlBody:q.body,attachments});
 process.stdout.write(JSON.stringify({request:q,denied:false,mime_base64:raw,reads}));
})().catch(e=>{process.stderr.write(e.stack);process.exit(1)});
