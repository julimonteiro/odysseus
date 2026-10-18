// Fork-owned Projects UI. Existing upstream chat/workspace tools remain authoritative.
import workspace from './workspace.js';
import ui from './ui.js';
import { terminalMode, fileReferences, alignDiff } from './projectDiff.js';

let sessions;
let state={projects:[],memberships:{}};
let refs=[];
let panelProject=null;
let activeProject=null;
let panel=null;
let autocomplete=null;
let requestSequence=0;
let fileSearchTimer=null;
const gitStates=new Map();
let gitRefreshBusy=false;
function branchLabel(id){const g=gitStates.get(id);return !g?'':g.unavailable?'Git unavailable':!g.repository?'No Git repository':g.detached?'detached '+(g.commit||'HEAD'):'⎇ '+g.branch;}
async function refreshGit(){
  if(gitRefreshBusy)return;gitRefreshBusy=true;
  try{for(const id of new Set([activeProject?.id,panelProject].filter(Boolean))){gitStates.set(id,await api('/'+id+'/git'));}
    renderComposer();
    if(panelProject&&el('project-branch'))el('project-branch').textContent=branchLabel(panelProject);
  }finally{gitRefreshBusy=false;}
}
const el=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(label,fn,cls='project-button')=>{const b=node('button',label,cls);b.type='button';b.addEventListener('click',()=>Promise.resolve().then(fn).catch(report));return b;};
function report(error){ui.showError(error?.message||String(error));}
async function api(path='',options={}) {
  const response=await fetch('/api/projects'+path,{credentials:'same-origin',...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...options.headers}});
  const data=await response.json();
  if(!response.ok)throw Object.assign(new Error(data.detail||'Project request failed'),{status:response.status});
  return data;
}
function project(id){return state.projects.find(p=>p.id===id);}
function sid(){return sessions?.getCurrentSessionId();}
export function isProjectSession(id){return Boolean(state.memberships[id]);}
export function onSessionChanged(id) {
  const next=project(state.memberships[id]);
  if(activeProject?.id!==next?.id)refs=[];
  const leaving=Boolean(activeProject);
  activeProject=next||null;
  if(activeProject)workspace.setWorkspace(activeProject.root);
  else if(leaving)workspace.setWorkspace('');
  renderComposer();renderTree();
  if(activeProject)refreshGit().catch(()=>{});
}
export async function refresh() {
  try {
    state=await api();
    const section=el('projects-section');if(section)section.hidden=false;
    onSessionChanged(sid());
    sessions?.renderSessionList();
  } catch(e) {
    if(e.status===403){if(el('projects-section'))el('projects-section').hidden=true;return;}
    throw e;
  }
}
function renderTree() {
  const list=el('project-list');if(!list)return;list.replaceChildren();
  const chats=sessions?.getSessions()||[];
  const visit=(parent,container)=>{
    for(const p of state.projects.filter(p=>(p.parent_id||null)===parent)) {
      const folder=node('div',undefined,'session-folder project-tree-folder');
      const header=node('div',undefined,'session-folder-header section-header-flex project-tree-header');
      const content=node('div',undefined,'session-folder-content');
      content.hidden=localStorage.getItem('project-open-'+p.id)==='false';
      const toggle=button(content.hidden?'▶':'▼',()=>{
        content.hidden=!content.hidden;toggle.textContent=content.hidden?'▶':'▼';
        toggle.setAttribute('aria-expanded',String(!content.hidden));
        localStorage.setItem('project-open-'+p.id,String(!content.hidden));
      },'folder-toggle project-tree-toggle');
      toggle.setAttribute('aria-label','Toggle '+p.name);toggle.setAttribute('aria-expanded',String(!content.hidden));
      const name=button(p.name,()=>openProject(p.id),'folder-name project-name section-title');name.title=p.root;
      const add=button('+',()=>createChat(p.id),'project-add-chat');add.title='New chat in '+p.name;add.setAttribute('aria-label',add.title);
      const remove=button('×',()=>deleteProject(p.id),'folder-delete-btn');remove.title='Delete project';remove.setAttribute('aria-label','Delete project '+p.name);
      header.append(toggle,name,add,remove);folder.append(header,content);
      for(const chat of chats.filter(s=>!s.archived&&state.memberships[s.id]===p.id)) {
        const row=node('div',undefined,'list-item session-item project-chat'+(chat.id===sid()?' active-session':''));
        row.setAttribute('role','button');row.tabIndex=0;row.append(node('span',chat.name,'grow'));
        row.addEventListener('click',()=>sessions.selectSession(chat.id,{keepSidebar:true}));
        row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();row.click();}});
        row.title=chat.name;content.append(row);
      }
      visit(p.id,content);container.append(folder);
    }
  };
  visit(null,list);
  if(!state.projects.length)list.append(node('p','Add a directory to start a project.','project-empty'));
}
function renderComposer() {
  const input=el('message');if(!input)return;
  const frame=input.closest('.chat-input-bar')||input.parentElement;
  frame.classList.toggle('project-terminal-mode',terminalMode(input.value));
  let badge=el('project-composer-mode');
  if(!badge){badge=node('div',undefined,'project-composer-mode');badge.id='project-composer-mode';badge.setAttribute('aria-live','polite');frame.insertBefore(badge,input.parentElement);}
  badge.hidden=!terminalMode(input.value)&&!activeProject;
  const projectLabel=activeProject?`▱ ${activeProject.name}${branchLabel(activeProject.id)?' · '+branchLabel(activeProject.id):''}`:'';
  badge.textContent=terminalMode(input.value)?`>_ Terminal · ${projectLabel||workspace.getWorkspace()||'choose a directory'}`:projectLabel;
  badge.title=activeProject?.root||'';
  if(el('chat-changes-btn'))el('chat-changes-btn').hidden=!sid();
  input.setAttribute('aria-description',terminalMode(input.value)?'Terminal mode: text after ! runs directly on the host, without AI.':'Message to AI');
  const send=document.querySelector('.send-btn');
  if(send){send.classList.toggle('project-terminal-send',terminalMode(input.value));if(terminalMode(input.value))send.title='Run terminal command';}
  let chips=el('project-reference-chips');
  if(!chips){chips=node('div',undefined,'project-reference-chips');chips.id='project-reference-chips';frame.insertBefore(chips,input.parentElement);}
  chips.replaceChildren();
  for(const path of refs)chips.append(button('@'+path+' ×',()=>{refs=refs.filter(x=>x!==path);renderComposer();},'project-reference-chip'));
}
export function decorateRequest(form,sessionId,message) {
  const p=project(state.memberships[sessionId]);
  if(!p)return;
  const paths=[...new Set([...refs,...fileReferences(message)])];
  form.set('project_id',p.id);form.set('project_files',JSON.stringify(terminalMode(message)?[]:paths));form.set('workspace',p.root);
  refs=[];renderComposer();
}
function dialog(title) {
  const overlay=node('div',undefined,'project-overlay');const box=node('section',undefined,'modal-content project-dialog');
  box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');box.setAttribute('aria-label',title);
  const header=node('header');header.append(node('h3',title),button('×',()=>overlay.remove(),'project-close'));box.append(header);overlay.append(box);document.body.append(overlay);
  overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.remove();});
  overlay.addEventListener('keydown',e=>{if(e.key==='Escape')overlay.remove();});
  return {overlay,box};
}
function inputField(label,value='') {
  const wrap=node('label',label,'project-field'),input=node('input');input.value=value;wrap.append(input);return {wrap,input};
}
export async function createProject(parentId=null) {
  const {overlay,box}=dialog(parentId?'New project folder':'New project');
  const form=node('form');const name=inputField('Name');name.input.required=true;name.input.maxLength=100;
  const root=inputField('Directory on the Odysseus host',parentId?project(parentId)?.root:'');root.input.required=true;
  form.append(name.wrap,root.wrap,button('Browse directories',()=>workspace.openWorkspaceBrowser({parentModal:overlay,returnFocus:root.input,initialPath:root.input.value,onSelect:p=>{root.input.value=p;}})));
  form.append(node('p','A project groups chats around an existing directory. Removing it does not delete your files.','project-note'));
  const submit=node('button','Create project','project-button project-primary');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async e=>{e.preventDefault();submit.disabled=true;try{const p=await api('',{method:'POST',body:JSON.stringify({name:name.input.value,root:root.input.value,parent_id:parentId})});overlay.remove();await refresh();await openProject(p.id);}catch(err){report(err);submit.disabled=false;}});
  box.append(form);name.input.focus();
}
async function createChat(projectId) {
  const p=project(projectId);if(!p)throw new Error('Project unavailable');
  const r=await fetch('/api/default-chat');if(!r.ok)throw new Error('Configure a default model first');const d=await r.json();
  const fd=new FormData();fd.set('name','New chat');fd.set('endpoint_url',d.endpoint_url||'');fd.set('model',d.model||'');fd.set('endpoint_id',d.endpoint_id||'');fd.set('skip_validation','true');
  const response=await fetch('/api/session',{method:'POST',body:fd});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Could not create chat');
  await api('/sessions/'+encodeURIComponent(data.id),{method:'PUT',body:JSON.stringify({project_id:projectId})});
  await refresh();await sessions.loadSessions();await sessions.selectSession(data.id,{keepSidebar:true});
  el('message')?.focus();return data.id;
}
async function moveCurrent(projectId) {
  if(!sid())throw new Error('Open a chat first');
  await api('/sessions/'+encodeURIComponent(sid()),{method:'PUT',body:JSON.stringify({project_id:projectId})});await refresh();
}
async function deleteProject(id) {
  const p=project(id);if(!p)return;
  if(!await ui.styledConfirm(`Delete project "${p.name}" and its project folders? Chats will return to Chats. Files on disk will be kept.`,{title:'Delete project',confirmText:'Delete project',danger:true}))return;
  await api('/'+id,{method:'DELETE'});
  if(panel){panel.hidden=true;panelProject=null;}
  await refresh();
}
export async function openProject(id) {
  const p=project(id);if(!p)return;
  panelProject=id;
  if(!panel){panel=node('section',undefined,'project-panel');panel.id='project-panel';panel.setAttribute('aria-label','Project workspace');document.body.append(panel);}
  panel.hidden=false;panel.replaceChildren();
  const header=node('header');header.append(node('h3',p.name),button('×',()=>{panel.hidden=true;},'project-close'));panel.append(header,node('p',p.root,'project-root'));
  const branch=node('span',branchLabel(id),'project-branch');branch.id='project-branch';panel.append(branch);refreshGit().catch(()=>{});
  const toolbar=node('div',undefined,'project-toolbar');toolbar.append(button('+ Chat',()=>createChat(id)),button('+ Project folder',()=>createProject(id)),button('Move current chat here',()=>moveCurrent(id)),button('Move chat to Chats',()=>moveCurrent(null)),button('Changes',()=>showReviews(id)));
  panel.append(toolbar,node('p','Use @ to select a file. Begin a message with ! to run a terminal command directly.','project-note'));
  const tabs=node('div',undefined,'project-toolbar');tabs.append(button('Files',()=>browseFiles(id,'.')),button('+ Directory on disk',async()=>{const path=await ui.styledPrompt?.('Directory path relative to project:');if(path){await api('/'+id+'/directories',{method:'POST',body:JSON.stringify({path})});await browseFiles(id,'.');}}),button('Delete project',()=>deleteProject(id)));panel.append(tabs);const body=node('div',undefined,'project-panel-body');body.id='project-panel-body';panel.append(body);
  await browseFiles(id,'.');
}
async function addReference(id,path) {
  if(state.memberships[sid()]!==id)await createChat(id);
  if(!refs.includes(path))refs.push(path);
  renderComposer();el('message')?.focus();
}
async function browseFiles(id,path) {
  const seq=++requestSequence;const data=await api('/'+id+'/browse?path='+encodeURIComponent(path));
  if(seq!==requestSequence||id!==panelProject)return;
  const body=el('project-panel-body');if(!body)return;body.replaceChildren(node('h4',path==='.'?'Files':path));
  if(path!=='.'){const parts=path.split('/');parts.pop();body.append(button('↑ Parent directory',()=>browseFiles(id,parts.join('/')||'.')));}
  for(const item of data.entries) {
    const row=node('div',undefined,'project-file-row');row.append(button((item.directory?'▱ ':'@ ')+item.name,()=>item.directory?browseFiles(id,item.path):addReference(id,item.path),'project-file-name'));body.append(row);
  }
  if(!data.entries.length)body.append(node('p','No visible files in this directory.','project-empty'));
}
async function showReviews(id) {
  const data=await api('/'+id+'/reviews');if(panelProject!==id)return;
  const body=el('project-panel-body');body.replaceChildren(node('h4','Changes'));
  body.append(node('p','Original on the left, current text on the right. Comparisons start before each project turn; concurrent manual edits may also appear.','project-note'));
  if(!data.reviews.length)body.append(node('p','Changes will appear after the first project turn.','project-empty'));
  for(const review of data.reviews) {
    const wrap=node('section',undefined,'project-review');const date=new Date(review.started*1000).toLocaleString();wrap.append(node('h4',date+' · '+review.status));
    const summary=review.summary;
    if(summary?.partial||review.status==='incomplete')wrap.append(node('p','Partial coverage — some changes may be omitted.','project-warning'));
    if(summary?.coverage?.excluded?.length)wrap.append(node('p',`${summary.coverage.excluded.length} exclusions (sensitive, binary, oversized or unreadable files).`,'project-note'));
    for(const file of summary?.changes||[])wrap.append(button(file.status+' · '+file.path,()=>showDiff(id,review.id,file.path),'project-changed-file'));
    if(summary&&!summary.changes.length)wrap.append(node('p',summary.partial?'No comparable changes in covered files.':'No eligible text changes.','project-empty'));
    body.append(wrap);
  }
}
export async function showConversationChanges() {
  const sessionId=sid();if(!sessionId)return;
  const {overlay,box}=dialog('Changes');
  box.append(node('p','Changes captured during this conversation. Concurrent manual edits can also appear.','project-note'));
  const body=node('div',undefined,'project-conversation-reviews');box.append(body);
  let cursor=null;
  const load=async()=>{
    const data=await api('/sessions/'+encodeURIComponent(sessionId)+'/reviews'+(cursor?'?cursor='+encodeURIComponent(cursor):''));
    if(!overlay.isConnected)return;
    body.querySelector('.project-load-older')?.remove();
    if(!data.reviews.length&&!cursor)body.append(node('p','No tracked changes in this conversation yet. Earlier untracked edits cannot be reconstructed.','project-empty'));
    for(const review of data.reviews){
      const wrap=node('section',undefined,'project-review');wrap.append(node('h4',new Date(review.started*1000).toLocaleString()+' · '+review.status));
      const summary=review.summary;
      if(!summary)wrap.append(node('p','Comparison will be available when this turn finishes.','project-note'));
      if(summary?.partial||review.status==='incomplete')wrap.append(node('p','Partial coverage — some changes may be omitted.','project-warning'));
      for(const file of summary?.changes||[])wrap.append(button(file.status+' · '+file.path,async()=>{
        const diff=await api('/sessions/'+encodeURIComponent(sessionId)+'/reviews/'+review.id+'/file?path='+encodeURIComponent(file.path));renderDiff(diff,file.path);
      },'project-changed-file'));
      if(summary&&!summary.changes.length)wrap.append(node('p','No eligible text changes in this turn.','project-note'));
      body.append(wrap);
    }
    cursor=data.next_cursor;
    if(cursor)body.append(button('Load older changes',load,'project-button project-load-older'));
  };
  await load();
}
async function showDiff(id,turn,path) {
  const file=await api('/'+id+'/reviews/'+turn+'/file?path='+encodeURIComponent(path));renderDiff(file,path);
}
function renderDiff(file,path) {
  const {box}=dialog(path);box.classList.add('project-diff-dialog');
  const result=alignDiff(file.before,file.after);
  if(result.truncated||result.approximate)box.append(node('p',result.truncated?'Display limited to 5,000 lines.':'Large change: approximate line alignment.','project-warning'));
  const title=node('div',undefined,'project-diff-head');title.append(node('strong','Original'),node('strong','Changed'));box.append(title);
  const grid=node('div',undefined,'project-diff-grid');
  for(const row of result.rows)for(const side of ['left','right']) {
    const value=row[side];const cell=node('div',undefined,'project-diff-cell '+(value?.kind||'empty')+' '+side);cell.append(node('span',value?String(value.line):'','project-line-number'),node('code',value?.text||''));grid.append(cell);
  }
  box.append(grid);
}
async function updateAutocomplete() {
  const input=el('message');if(!input||!activeProject||terminalMode(input.value)){autocomplete?.remove();autocomplete=null;return;}
  const left=input.value.slice(0,input.selectionStart);const match=left.match(/(?:^|\s)@([^\s@{}]*)$/);if(!match){autocomplete?.remove();autocomplete=null;return;}
  const seq=++requestSequence,pid=activeProject.id;const data=await api('/'+pid+'/files?q='+encodeURIComponent(match[1]));
  if(seq!==requestSequence||activeProject?.id!==pid)return;
  autocomplete?.remove();autocomplete=node('div',undefined,'project-autocomplete');autocomplete.setAttribute('aria-label','Project file suggestions');
  for(const path of data.files.slice(0,12))autocomplete.append(button(path,()=>{
    const start=input.selectionStart-match[1].length-1;input.setRangeText('',start,input.selectionStart,'end');refs.push(path);refs=[...new Set(refs)];autocomplete.remove();autocomplete=null;renderComposer();input.focus();
  },'project-file-suggestion'));
  if(!data.files.length)autocomplete.append(node('span','No matching text files.'));
  input.parentElement.append(autocomplete);
}
export async function initProjects(sessionModule) {
  sessions=sessionModule;
  el('chat-changes-btn')?.addEventListener('click',()=>showConversationChanges().catch(report));
  el('project-create-btn')?.addEventListener('click',()=>createProject().catch(report));
  const input=el('message');
  input?.addEventListener('input',()=>{renderComposer();clearTimeout(fileSearchTimer);fileSearchTimer=setTimeout(()=>updateAutocomplete().catch(report),180);});
  input?.addEventListener('keydown',e=>{if(e.key==='Escape'){autocomplete?.remove();autocomplete=null;}});
  setInterval(()=>{renderComposer();refreshGit().catch(()=>{});if(panelProject&&panel&&!panel.hidden&&el('project-panel-body')?.querySelector('.project-review'))showReviews(panelProject).catch(()=>{});},5000);
  await refresh();
}
export default {initProjects,refresh,onSessionChanged,isProjectSession,decorateRequest,openProject};
