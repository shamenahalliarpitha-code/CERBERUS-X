const $ = (id) => document.getElementById(id);
let currentData = {documents:[], facts:[], conflicts:[], graph:{nodes:[],edges:[]}};

function showView(name){
  document.querySelectorAll(".view").forEach(v=>v.classList.remove("active"));
  document.querySelectorAll(".nav").forEach(v=>v.classList.remove("active"));
  $("view-"+name).classList.add("active");
  const nav=document.querySelector(`.nav[data-view="${name}"]`);
  if(nav) nav.classList.add("active");
  const titles={overview:"Overview",documents:"Evidence library",conflicts:"Contradiction analysis",graph:"Knowledge graph",assistant:"Evidence assistant"};
  $("page-title").textContent=titles[name];
}
document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.view)));
document.querySelectorAll("[data-jump]").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.jump)));

async function refresh(){
  const r=await fetch("/api/data"); currentData=await r.json();
  const s=currentData.summary;
  $("metric-docs").textContent=s.documents; $("metric-facts").textContent=s.facts;
  $("metric-conflicts").textContent=s.contradictions; $("metric-review").textContent=s.needs_review;
  $("doc-count").textContent=`${s.documents} files`;
  renderDocuments(); renderConflicts(); renderGraph();
}
function renderDocuments(){
  const docs=currentData.documents;
  $("recent-docs").innerHTML=docs.length?docs.slice(-4).reverse().map(d=>`<div class="workflow"><div><b>▤</b><span><strong>${esc(d.filename)}</strong><small>${d.file_type} · ${d.characters} characters · ${esc(d.status)}</small></span></div></div>`).join(""):'<div class="empty">No documents yet. Upload files to begin.</div>';
  $("document-table").innerHTML=docs.length?docs.map(d=>`<tr><td class="file-name">${esc(d.filename)}</td><td><span class="tag">${esc(d.file_type)}</span></td><td>${d.characters.toLocaleString()}</td><td class="status-ok">${esc(d.status)}</td></tr>`).join(""):'<tr><td colspan="4" class="empty">No documents uploaded.</td></tr>';
}
function renderConflicts(){
  const list=currentData.conflicts;
  $("conflict-list").innerHTML=list.length?list.map(c=>`<div class="conflict-card"><div class="conflict-title">⚠ ${esc(c.category)} conflict</div><div class="claim-grid"><div class="claim"><small>SOURCE A · ${esc(c.source_a)}</small><p>${esc(c.claim_a)}</p><b>${esc(c.value_a)}</b></div><div class="claim"><small>SOURCE B · ${esc(c.source_b)}</small><p>${esc(c.claim_b)}</p><b>${esc(c.value_b)}</b></div></div><div class="explanation">${esc(c.explanation)}</div></div>`).join(""):'<div class="empty panel">No contradictions detected yet. Upload documents containing comparable claims.</div>';
}
function renderGraph(){
  const svg=$("graph-svg"), nodes=currentData.graph.nodes, edges=currentData.graph.edges;
  if(!nodes.length){svg.innerHTML='<text x="450" y="240" text-anchor="middle" fill="#7b8798">Upload evidence to build the graph</text>';return;}
  const cx=450,cy=235, radius=150;
  const pos={}; nodes.forEach((n,i)=>{const angle=(2*Math.PI*i/nodes.length)-Math.PI/2;pos[n.id]={x:cx+radius*Math.cos(angle),y:cy+radius*Math.sin(angle)}});
  let markup="";
  edges.forEach(e=>{const a=pos[e.from],b=pos[e.to];if(a&&b)markup+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#cbd3e5" stroke-width="2"/><text x="${(a.x+b.x)/2}" y="${(a.y+b.y)/2-7}" text-anchor="middle" font-size="9" fill="#8993a6">${esc(e.label).slice(0,18)}</text>`});
  nodes.forEach(n=>{const p=pos[n.id], color=n.kind==="property"?"#667fe8":"#36a883";markup+=`<circle cx="${p.x}" cy="${p.y}" r="28" fill="${color}" opacity=".13"/><circle cx="${p.x}" cy="${p.y}" r="21" fill="${color}"/><text x="${p.x}" y="${p.y+4}" text-anchor="middle" font-size="9" font-weight="700" fill="white">${esc(n.label).slice(0,12)}</text>`});
  svg.innerHTML=markup;
}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

async function uploadFiles(fileList){
  if(!fileList.length)return;
  const form=new FormData(); [...fileList].forEach(f=>form.append("files",f));
  const msg=$("upload-message");msg.className="message";msg.textContent="Processing files locally…";
  try{
    const response=await fetch("/api/upload",{method:"POST",body:form});
    const data=await response.json(); if(!response.ok)throw new Error(data.detail||"Upload failed");
    const done=data.processed.map(x=>`${x.filename}: ${x.facts} candidate claims extracted`).join(" · ");
    const errors=data.errors.map(x=>`${x.filename}: ${x.error}`).join(" · ");
    msg.textContent=[done,errors].filter(Boolean).join(" | ")||"No supported files were processed.";
    if(data.errors.length)msg.classList.add("error");
    await refresh();
  }catch(e){msg.className="message error";msg.textContent=e.message;}
  $("file-input").value="";
}
$("file-input").addEventListener("change",e=>uploadFiles(e.target.files));
const drop=$("drop-zone");
drop.addEventListener("dragover",e=>{e.preventDefault();drop.style.borderColor="#526fe5"});
drop.addEventListener("dragleave",()=>drop.style.borderColor="#cbd3e6");
drop.addEventListener("drop",e=>{e.preventDefault();drop.style.borderColor="#cbd3e6";uploadFiles(e.dataTransfer.files)});

$("chat-form").addEventListener("submit",async e=>{
  e.preventDefault();const q=$("chat-input").value.trim();if(!q)return;
  addMessage(q,"user");$("chat-input").value="";
  try{const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});const d=await r.json();addMessage(d.answer,"bot");}
  catch(err){addMessage("Unable to contact the local backend. Is the server running?","bot");}
});
function addMessage(text,kind){const d=document.createElement("div");d.className=kind==="user"?"user-message":"bot-message";d.textContent=text;$("chat-messages").appendChild(d);$("chat-messages").scrollTop=$("chat-messages").scrollHeight;}
document.querySelectorAll(".suggestion").forEach(b=>b.addEventListener("click",()=>{$("chat-input").value=b.textContent;$("chat-form").requestSubmit();}));
$("reset-btn").addEventListener("click",async()=>{if(!confirm("Clear all documents and results from this session?"))return;await fetch("/api/reset",{method:"DELETE"});$("upload-message").className="message hidden";$("chat-messages").innerHTML='<div class="bot-message">Session cleared. Upload documents to begin again.</div>';await refresh();});
refresh();

const logoutButton = $("logout-btn");
if (logoutButton) logoutButton.addEventListener("click", async () => {
  await fetch("/api/auth/logout", {method:"POST"});
  window.location.href = "/";
});
