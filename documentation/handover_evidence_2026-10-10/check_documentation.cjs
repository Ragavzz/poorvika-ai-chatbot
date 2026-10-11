const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const docs = ['README.md','documentation/FINAL_PROJECT_HANDOVER.md','documentation/ARCHITECTURE.md','documentation/API_REFERENCE.md','documentation/TESTING_AND_BENCHMARKS.md','documentation/DEPLOYMENT_AND_OPERATIONS.md'];
const issues = [];
const counts = {documents:docs.length,localLinks:0,anchors:0,mermaidBlocks:0};
const slug = s => s.toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu,'').replace(/\s/g,'-');
for (const file of docs) {
 const text = fs.readFileSync(path.join(root,file),'utf8');
 const lines=text.split('\n');
 if (!text.endsWith('\n')) issues.push({file,type:'missing final newline'});
 if (lines.some(l=>/[ \t]+$/.test(l))) issues.push({file,type:'trailing whitespace'});
 if (lines.filter(l=>l.startsWith('```')).length % 2) issues.push({file,type:'unbalanced fences'});
 counts.mermaidBlocks += (text.match(/```mermaid/g)||[]).length;
 for(const m of text.matchAll(/\[[^\]\n]+\]\(([^)]+)\)/g)){
  const target=m[1];
  if (/^(https?:|mailto:)/.test(target)) continue;
  counts.localLinks++;
  const [relative,anchor]=target.split('#');
  const full=relative?path.resolve(path.dirname(path.join(root,file)),relative):path.join(root,file);
  if(!fs.existsSync(full)){issues.push({file,type:'missing local link',target});continue;}
  if(anchor){
   counts.anchors++;
   const headings=fs.readFileSync(full,'utf8').split('\n').filter(l=>/^#+ /.test(l)).map(l=>slug(l.replace(/^#+ /,'')));
   if(!headings.includes(anchor))issues.push({file,type:'missing heading anchor',target});
  }
 }
 if (/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,})|postgres(?:ql)?(?:\+psycopg)?:\/\/[^\s/:<>]+:[^\s/@<>]+@/.test(text)) issues.push({file,type:'credential/private-key pattern'});
 for(const line of lines) if(/^\|/.test(line) && !line.endsWith('|')) issues.push({file,type:'malformed table row',line});
}
const output={checked_at_utc:new Date().toISOString(),scope:'New/updated handover Markdown only; bounded secret patterns, file links/anchors/fences/trailing whitespace. Not an exhaustive secret or rendered-Mermaid audit.',counts,issues,pass:issues.length===0};
fs.writeFileSync(path.join(__dirname,'documentation_checks.json'),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify(output,null,2));
if(issues.length)process.exitCode=1;
