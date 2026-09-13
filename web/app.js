'use strict';
const $ = (id) => document.getElementById(id);
const state = { meta: null, items: [], selected: null, node: null, request: 0, selectionRequest: 0, zoom: 1, x: 0, y: 0 };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`요청 실패 (${response.status})`);
  return response.json();
}
function notice(message, error=false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function currentHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  return { wf: params.get('wf'), node: params.get('node') };
}
function saveHash() {
  if (!state.selected) return;
  const params = new URLSearchParams({wf: state.selected.id});
  if (state.node) params.set('node', state.node.id);
  history.replaceState(null, '', `#${params}`);
}
function tags(w) { return [...w.phases.map(p => `<span class="tag">${esc(p)}</span>`), ...w.agencies.map(a => `<span class="tag agency">${esc(a)}</span>`)].join(''); }
async function search() {
  const request = ++state.request;
  ++state.selectionRequest;
  $('workspace').setAttribute('aria-busy','true');
  try {
    const params = new URLSearchParams({q:$('search').value.trim(),phase:$('phase').value,agency:$('agency').value});
    const result = await api(`/api/workflows?${params}`);
    if (request !== state.request) return;
    state.items = result.items;
    $('result-count').textContent = result.total;
    notice(`${result.total}개 워크플로우 · 검색 범위: 업무명, 관련 기관·부서, 조치 원문`);
    renderCatalog();
    if (!result.total) {
      state.selected = null; state.node = null;
      $('selected-workflow').hidden = true; $('selection-empty').hidden = false;
      history.replaceState(null, '', location.pathname);
      return;
    }
    const requested = currentHash();
    const selected = result.items.find(w => w.id === requested.wf) || result.items.find(w => w.id === state.selected?.id) || result.items[0];
    await selectWorkflow(selected.id, requested.node);
  } catch (error) {
    if (request !== state.request) return;
    notice(`${error.message}. 페이지를 새로고침하거나 검색을 다시 시도하세요.`,true);
    state.selected=null; state.node=null; state.items=[];
    renderCatalog(); $('result-count').textContent='0';
    $('selected-workflow').hidden=true; $('selection-empty').hidden=true;
  } finally { if(request===state.request) $('workspace').setAttribute('aria-busy','false'); }
}
function renderCatalog() {
  $('workflow-list').innerHTML = state.items.length ? state.items.map(w => `<button class="workflow-card ${state.selected?.id === w.id?'active':''}" data-wf="${esc(w.id)}" aria-pressed="${state.selected?.id===w.id}"><span class="wid">${esc(w.id)}</span><strong>${esc(w.title)}</strong><small>${esc(w.phases.join(' · '))} <span aria-hidden="true">/</span> ${w.nodes.length}개 조치</small></button>`).join('') : '<p class="empty">검색 결과가 없습니다.</p>';
  $('workflow-list').querySelectorAll('button').forEach(button => button.addEventListener('click', () => selectWorkflow(button.dataset.wf)));
}
async function selectWorkflow(id, nodeId) {
  const request = ++state.selectionRequest;
  $('selected-workflow').hidden = true;
  try {
    const w = await api(`/api/workflows/${encodeURIComponent(id)}`);
    if (request !== state.selectionRequest) return;
    state.selected=w; state.node=w.nodes.find(n=>n.id===nodeId)||w.nodes[0];
    state.zoom=1; state.x=0; state.y=0;
    $('selection-empty').hidden=true; $('selected-workflow').hidden=false;
    $('selected-id').textContent=w.id;
    $('selected-title').textContent=w.title;
    $('selected-tags').innerHTML=tags(w);
    renderCatalog(); renderActions(); renderGraph(); renderEvidence(); saveHash();
  } catch(error) { if(request===state.selectionRequest) notice(`${error.message}. 업무를 다시 선택하세요.`,true); }
}
function selectNode(id) {
  state.node=state.selected.nodes.find(n=>n.id===id)||state.selected.nodes[0];
  renderActions(); renderGraph(); renderEvidence(); saveHash();
}
function renderActions() {
  $('action-list').innerHTML=state.selected.nodes.map(n=>`<button class="action-item ${n.id===state.node.id?'active':''}" data-node="${n.id}" aria-pressed="${n.id===state.node.id}"><strong>${esc(n.id)} · ${esc(n.label)}</strong><p>${esc(n.text)}</p><small>원문 근거 확인 ↗</small></button>`).join('');
  $('action-list').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>selectNode(b.dataset.node)));
}
function wrap(text, length=17) {
  const chars=Array.from(text), lines=[];
  while(chars.length) lines.push(chars.splice(0,length).join(''));
  return lines;
}
function renderGraph() {
  const w=state.selected;
  // A source-backed inclusion graph, not an invented mandatory procedure sequence.
  const root={id:w.id,label:w.title,x:30,y:200,width:240,height:94};
  const positions=w.nodes.map((n,i)=>({...n,x:410+(i%2)*270,y:30+Math.floor(i/2)*155,width:240,height:94}));
  const height=Math.max(490,Math.ceil(positions.length/2)*155+30);
  state.graphHeight=height;
  const lookup=new Map([root,...positions].map(n=>[n.id,n]));
  let markup='<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#196a55"/></marker></defs>';
  markup+='<g id="graph-scene">';
  for(const edge of w.edges) {
    const from=lookup.get(edge.source),to=lookup.get(edge.target);
    if(edge.kind==='contains') {
      const startX=from.x+from.width,startY=from.y+from.height/2,endY=to.y+to.height/2;
      // Route inclusion branches outside the left node column to avoid passing through cards.
      if(to.x>410) {
        const laneY=to.y-16;
        markup+=`<path class="graph-edge" d="M${startX} ${startY} H325 V${laneY} H${to.x+120} V${to.y}"/>`;
      } else markup+=`<path class="graph-edge" d="M${startX} ${startY} H325 V${endY} H${to.x}"/>`;
    } else {
      const y=from.y+from.height+18;
      markup+=`<path class="graph-arrow" marker-end="url(#arrow)" d="M${from.x+120} ${from.y+from.height} V${y} H${to.x+120} V${to.y+to.height}"/><text class="edge-label" x="${from.x+130}" y="${y+13}">${esc(edge.label)}</text>`;
    }
  }
  for(const n of [root,...positions]) {
    const isRoot=n.id===w.id;
    markup+=`<g class="graph-node ${isRoot?'graph-root':''} ${state.node.id===n.id?'selected':''}" data-node="${esc(n.id)}" role="button" tabindex="0" aria-label="${esc(n.id+' '+n.label)}" aria-pressed="${state.node.id===n.id}" transform="translate(${n.x},${n.y})"><rect width="${n.width}" height="${n.height}" rx="8"/><text class="node-id" x="15" y="20">${esc(n.id)}</text>`;
    wrap(n.label).forEach((line,i)=>{markup+=`<text class="node-label" x="15" y="${43+i*18}">${esc(line)}</text>`;});
    markup+=`<text class="node-source" x="15" y="80">${isRoot?`${w.nodes.length}개 수록 조치`:'원문 근거 ↗'}</text></g>`;
  }
  markup+='</g>';
  $('graph').innerHTML=markup; transformGraph();
  $('graph').querySelectorAll('.graph-node').forEach(n=>{
    const activate=()=>selectNode(n.dataset.node);
    n.addEventListener('click',activate);
    n.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();activate();}});
  });
}
function transformGraph() {
  const width=960/state.zoom,height=(state.graphHeight||490)/state.zoom;
  $('graph').setAttribute('viewBox',`${state.x} ${state.y} ${width} ${height}`);
}
function renderEvidence() {
  const n=state.node;
  $('evidence-content').innerHTML=`<h4>${esc(n.label)}</h4>`+n.evidenceIds.map(id=>{
    const e=state.selected.evidence[id];
    return `<p class="reference-heading">${esc(e.heading)}</p><blockquote>${esc(e.quote)}</blockquote><p class="locator">${esc(e.member)} · XML 요소 ${e.elementIndex} · 문단 ID ${esc(e.paragraphId)}</p><div class="evidence-links"><a href="/api/evidence/${encodeURIComponent(id)}" target="_blank" rel="noopener">근거 데이터 열기 ↗</a><a href="/source-excerpts.xml" download>원문 XML 발췌 다운로드 ↓</a></div>`;
  }).join('');
}
function setTab(graph) {
  for(const [id,on] of [['graph',graph],['actions',!graph]]) {
    $(`${id}-tab`).setAttribute('aria-selected',String(on)); $(`${id}-tab`).tabIndex=on?0:-1; $(`${id}-panel`).hidden=!on;
  }
}
$('graph-tab').addEventListener('click',()=>setTab(true));
$('actions-tab').addEventListener('click',()=>setTab(false));
document.querySelector('.view-tabs').addEventListener('keydown',event=>{
  if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) {
    event.preventDefault(); const graph=event.key==='Home'||(event.key!=='End'&&$('graph-tab').getAttribute('aria-selected')!=='true');
    setTab(graph); $(graph?'graph-tab':'actions-tab').focus();
  }
});
let timer;
$('search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(search,180);});
for(const id of ['phase','agency']) $(id).addEventListener('change',()=>{clearTimeout(timer);search();});
$('reset').addEventListener('click',()=>{clearTimeout(timer);for(const id of ['search','phase','agency']) $(id).value='';search();});
$('zoom-in').addEventListener('click',()=>{state.zoom=Math.min(2.5,state.zoom+.2);transformGraph();});
$('zoom-out').addEventListener('click',()=>{state.zoom=Math.max(.5,state.zoom-.2);transformGraph();});
$('zoom-reset').addEventListener('click',()=>{state.zoom=1;state.x=0;state.y=0;transformGraph();});
let drag=null;
$('graph').addEventListener('pointerdown',e=>{if(e.target.closest('.graph-node'))return;drag={px:e.clientX,py:e.clientY,x:state.x,y:state.y};$('graph').setPointerCapture(e.pointerId);$('graph').classList.add('dragging');});
$('graph').addEventListener('pointermove',e=>{if(!drag)return;const ratio=$('graph').viewBox.baseVal.width/$('graph').getBoundingClientRect().width;state.x=drag.x-(e.clientX-drag.px)*ratio;state.y=drag.y-(e.clientY-drag.py)*ratio;transformGraph();});
for(const event of ['pointerup','pointercancel','lostpointercapture']) $('graph').addEventListener(event,()=>{drag=null;$('graph').classList.remove('dragging');});
$('copy-link').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);notice('현재 워크플로우·조치 링크를 복사했습니다.');}catch{notice('주소 표시줄의 현재 URL을 복사해 주세요.');}});
$('source-info').addEventListener('click',()=>{if(state.meta)$('source-dialog').showModal();});
$('close-dialog').addEventListener('click',()=>$('source-dialog').close());
window.addEventListener('hashchange',()=>{
  const h=currentHash();
  if(!/^WF-\d{3}$/.test(h.wf||''))return;
  clearTimeout(timer);
  if(state.items.some(w=>w.id===h.wf))selectWorkflow(h.wf,h.node);
  else {
    // An incoming shared link takes precedence over filters from the previous view.
    for(const id of ['search','phase','agency'])$(id).value='';
    search();
  }
});
async function boot() {
  try {
    state.meta=await api('/api/meta'); const m=state.meta;
    $('workflow-count').textContent=m.workflowCount; $('node-count').textContent=m.nodeCount;
    for(const [id,values] of [['phase',m.phases],['agency',m.agencies]]) for(const value of values) {const option=document.createElement('option');option.value=value;option.textContent=value;$(id).append(option);}
    $('source-content').innerHTML=`<p><strong>${esc(m.source.title)}</strong><br>${esc(m.source.publisher)} · ${esc(m.source.edition)}</p><p>${esc(m.editorialNote)}</p><p>${esc(m.source.locatorNote)} ${esc(m.source.extractionNote)}</p><p>원천 파일: ${esc(m.source.filename)}</p><p>원천 파일 SHA-256<br><code>${esc(m.source.sha256)}</code></p><p>서비스에는 업무 관련 원문 발췌를 수록했습니다. 전체 HWPX는 포함하지 않습니다.</p><a href="/source-excerpts.xml" download>원문 XML 발췌 다운로드 ↓</a>`;
    await search();
  } catch(error){notice(`초기 데이터를 불러오지 못했습니다. ${error.message}. 새로고침해 주세요.`,true);}
}
boot();
