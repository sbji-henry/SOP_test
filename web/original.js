'use strict';
const $ = (id) => document.getElementById(id);
const hazards = {wildfire:'산불','typhoon-rain':'태풍·호우',snow:'대설'};
const params = new URLSearchParams(location.search);
const disaster = Object.hasOwn(hazards, params.get('disaster')) ? params.get('disaster') : 'wildfire';
const wf = params.get('wf') || '';
const nodeId = params.get('node') || '';
const evidenceParam = params.get('evidence') || '';
let scale = 1;
let workflow = null;
let node = null;
let evidence = null;

function setText(id, value) { $(id).textContent = value ?? '—'; }
function notice(message, error=false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
async function json(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`요청 실패 (${response.status})`);
  return response.json();
}
function sopHash() {
  const p = new URLSearchParams({disaster});
  if (wf) p.set('wf', wf);
  if (nodeId) p.set('node', nodeId);
  return '/#' + p.toString();
}
function setLinks(evidenceId) {
  const back = sopHash();
  $('home-link').href = back;
  $('back-link').href = back;
  $('return-sop').href = back;
  $('download-source').href = `/manuals/${disaster}/source-excerpts.xml`;
  $('source-xml').href = `/manuals/${disaster}/source-excerpts.xml`;
  $('evidence-json').href = evidenceId ? `/api/disasters/${disaster}/evidence/${encodeURIComponent(evidenceId)}` : '#';
  $('evidence-json').classList.toggle('disabled', !evidenceId);
}
function render() {
  const source = evidence?.source || {};
  setText('publisher-label', [source.publisher, source.edition].filter(Boolean).join(' · '));
  setText('document-title', evidence?.heading || node?.label || '원문 근거');
  setText('document-subtitle', workflow ? `${workflow.id} · ${workflow.title}` : '원천 문서 근거');
  setText('paper-source', [source.publisher, source.title, source.edition].filter(Boolean).join(' · '));
  setText('source-heading', evidence?.heading || '원문 근거');
  setText('source-quote', evidence?.quote || '원문 근거를 찾을 수 없습니다.');
  const locator = evidence ? `${evidence.member || 'XML'} · 요소 ${evidence.elementIndex ?? '—'} · 문단 ID ${evidence.paragraphId || '—'}` : '—';
  setText('source-locator', locator);
  setText('evidence-id', evidence?.id);
  setText('evidence-heading', evidence?.heading);
  setText('evidence-member', evidence?.member);
  setText('evidence-index', evidence?.elementIndex);
  setText('evidence-paragraph', evidence?.paragraphId);
  setText('evidence-sha', evidence?.sha256);
  setText('compare-source', evidence?.quote);
  setText('compare-action', node?.text || '비교할 조치를 선택하지 않았습니다.');
  setText('meta-title', source.title);
  setText('meta-publisher', source.publisher);
  setText('meta-edition', source.edition);
  setText('meta-filename', source.filename);
  setText('meta-disaster', hazards[disaster]);
  setText('meta-workflow', workflow ? `${workflow.id} · ${workflow.title}` : '직접 근거 조회');
  setText('meta-node', node ? `${node.id} · ${node.label}` : '—');
  setText('workflow-crumb', workflow?.id || '원문 근거');

  const match = $('match-result');
  if (!node || !evidence) {
    match.className = 'match-result neutral'; match.textContent = '비교 대상 없음';
  } else if (node.text === evidence.quote) {
    match.className = 'match-result match'; match.textContent = '원문과 서비스 조치 문구가 일치합니다.';
  } else {
    match.className = 'match-result mismatch'; match.textContent = '원문과 서비스 조치 문구가 다릅니다. 원문을 기준으로 검토하세요.';
  }
  setLinks(evidence?.id);
}
async function boot() {
  try {
    if (wf) {
      workflow = await json(`/api/disasters/${disaster}/workflows/${encodeURIComponent(wf)}`);
      node = workflow.nodes.find(n => n.id === nodeId) || workflow.nodes[0] || null;
      const evidenceId = evidenceParam || node?.evidenceIds?.[0] || workflow.evidenceIds?.[0];
      if (!evidenceId) throw new Error('연결된 원문 근거가 없습니다.');
      evidence = await json(`/api/disasters/${disaster}/evidence/${encodeURIComponent(evidenceId)}`);
    } else if (evidenceParam) {
      evidence = await json(`/api/disasters/${disaster}/evidence/${encodeURIComponent(evidenceParam)}`);
    } else {
      throw new Error('워크플로우 또는 근거 ID가 필요합니다.');
    }
    render();
    notice('원문 근거와 추적 정보를 불러왔습니다.');
  } catch (error) {
    notice(`원문을 불러오지 못했습니다. ${error.message}`, true);
    setLinks('');
  }
}
function setTab(name) {
  document.querySelectorAll('[role=tab]').forEach(tab => {
    const on = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', String(on));
    tab.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll('[data-panel]').forEach(panel => panel.hidden = panel.dataset.panel !== name);
}
document.querySelectorAll('[role=tab]').forEach(tab => tab.addEventListener('click', () => setTab(tab.dataset.tab)));
$('.tabs').addEventListener('keydown', event => {
  const tabs = [...document.querySelectorAll('[role=tab]')];
  const current = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
  let next = current;
  if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
  if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
  if (next !== current) { event.preventDefault(); setTab(tabs[next].dataset.tab); tabs[next].focus(); }
});
function applyZoom() {
  $('paper').style.transform = `scale(${scale})`;
  $('zoom-label').textContent = Math.round(scale * 100) + '%';
}
$('zoom-in').addEventListener('click', () => { scale = Math.min(1.4, +(scale + .1).toFixed(1)); applyZoom(); });
$('zoom-out').addEventListener('click', () => { scale = Math.max(.7, +(scale - .1).toFixed(1)); applyZoom(); });
$('zoom-reset').addEventListener('click', () => { scale = 1; applyZoom(); });
$('copy-link').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(location.href); notice('원문보기 링크를 복사했습니다.'); }
  catch { notice('브라우저 주소를 직접 복사해 주세요.'); }
});
boot();