/* Pure geometry around native viewers. No file handles, widget state or React moves. */
(() => {
  'use strict';
  const VERSION = 'source-dock-20261005-2';
  if (window.__qmSourceDock?.version === VERSION) { window.__qmSourceDock.refresh(); return; }
  window.__qmSourceDock?.dispose();
  const abort = new AbortController(), desktop = matchMedia('(min-width:1001px)'), reduced = matchMedia('(prefers-reduced-motion:reduce)');
  const mounted = new Map(), departing = new Map(), prepared = new Map(), riskOrigins = new Map(), effects = new Set(), papers = new Set();
  const html = document.documentElement;
  let frame = 0, restoreFrame = 0, restoreSettle = 0, disposed = false;
  html.dataset.qmSourceDock = VERSION;
  const active = () => !disposed && !document.hidden && !reduced.matches && desktop.matches;
  const box = node => {
    if (!node?.isConnected) return null;
    const rect = node.getBoundingClientRect();
    return [rect.left, rect.top, rect.width, rect.height].every(Number.isFinite) && rect.width > 0 && rect.height > 0 ?
      {left:rect.left,top:rect.top,width:rect.width,height:rect.height} : null;
  };
  const inView = rect => rect && rect.left + rect.width > 0 && rect.top + rect.height > 0 && rect.left < innerWidth && rect.top < innerHeight;
  const selector = key => '.st-key-' + CSS.escape(key);
  const panelFor = marker => marker.closest(selector(marker.dataset.sourceDockPanel));
  function report(prefix, identity) {
    return [...document.querySelectorAll('[data-report-reader][data-report-prefix]')]
      .find(node => node.dataset.reportPrefix === prefix && (!identity || node.dataset.reportReader === identity));
  }
  function descriptor(node, prefix) {
    if (!node) return null;
    const root = node.closest('[data-report-reader]'), chapter = node.closest('[data-report-chapter]');
    if (!root) return {kind:'id',id:node.id,prefix,top:node.getBoundingClientRect().top};
    return {kind:node.hasAttribute('data-report-line')?'line':'source',prefix,reader:root.dataset.reportReader,
      chapter:chapter?.dataset.reportChapter,line:node.dataset.reportLine,source:node.dataset.reportSourceId,
      top:node.getBoundingClientRect().top};
  }
  function findAnchor(anchor) {
    if (!anchor) return null;
    if (anchor.kind === 'id') return document.getElementById(anchor.id);
    const root = report(anchor.prefix, anchor.reader);
    const chapter = root?.querySelector('[data-report-chapter="' + CSS.escape(anchor.chapter || '') + '"]');
    return chapter?.querySelector(anchor.kind === 'line' ? '[data-report-line="' + CSS.escape(anchor.line || '') + '"]' :
      '[data-report-source-id="' + CSS.escape(anchor.source || '') + '"]') || null;
  }
  function captureReading(prefix, fallback) {
    const root = report(prefix);
    if (!root) return fallback;
    const main = root.closest('[data-testid="stMain"]');
    const top = (main ? Math.max(0, main.getBoundingClientRect().top) : 0) + 135;
    const lines = [...root.querySelectorAll('[data-report-line]')];
    const chosen = lines.find(node => { const rect=node.getBoundingClientRect();return rect.bottom >= top && rect.top < innerHeight; });
    return chosen ? descriptor(chosen, prefix) : fallback;
  }
  function cancelRestore() {
    if (restoreFrame) cancelAnimationFrame(restoreFrame);
    if (restoreSettle) cancelAnimationFrame(restoreSettle);
    restoreFrame = restoreSettle = 0;
  }
  function compensate(anchor) {
    const node = findAnchor(anchor);
    if (!node || !desktop.matches || document.hidden) return;
    const delta = node.getBoundingClientRect().top - anchor.top;
    const scroller = node.closest('[data-testid="stMain"]') || document.scrollingElement;
    if (scroller && Number.isFinite(delta) && Math.abs(delta) > .5) scroller.scrollTop += delta;
  }
  function restoreReading(anchor) {
    if (!anchor || !desktop.matches) return;
    cancelRestore();
    restoreFrame = requestAnimationFrame(() => {
      restoreFrame = 0; compensate(anchor);
      restoreSettle = requestAnimationFrame(() => { restoreSettle = 0; compensate(anchor); });
    });
  }
  function prepare(link) {
    const root = link?.closest('[data-report-reader]');
    if (!root) return;
    const prefix = root.dataset.reportPrefix, id = link.dataset.reportSourceId;
    if (!prefix || !id) return;
    prepared.set(prefix + '|' + id, {origin:descriptor(link,prefix),box:box(link),reading:descriptor(link,prefix),started:performance.now()});
    if (prepared.size > 20) prepared.delete(prepared.keys().next().value);
  }
  function cancelVisuals() {
    for (const animation of effects) animation.cancel();
    effects.clear(); for (const paper of papers) paper.remove(); papers.clear();
    for (const state of [...mounted.values(),...departing.values()]) {state.flight=null;state.animation=null;}
    departing.clear();
  }
  function stopFlight(state) {
    const current=box(state.flight);
    if(state.animation){state.animation.cancel();effects.delete(state.animation);state.animation=null;}
    if(state.flight){papers.delete(state.flight);state.flight.remove();state.flight=null;}
    return current;
  }
  function flight(state, from, to, closing=false) {
    if (!active() || !inView(from) || !inView(to)) return;
    const paper = document.createElement('div');paper.className='qm-source-paper';paper.inert=true;paper.setAttribute('aria-hidden','true');
    const line=document.createElement('i');paper.appendChild(line);
    Object.assign(paper.style,{left:to.left+'px',top:to.top+'px',width:to.width+'px',height:to.height+'px'});
    document.body.appendChild(paper);papers.add(paper);state.flight=paper;
    if (!paper.animate) { paper.remove();papers.delete(paper);state.flight=null;return; }
    const animation=paper.animate([
      {transform:'translate('+(from.left-to.left)+'px,'+(from.top-to.top)+'px) scale('+(from.width/to.width)+','+(from.height/to.height)+')',opacity:.88},
      {transform:'translate(0px,0px) scale(1,1)',opacity:0}
    ],{duration:closing?560:680,easing:'cubic-bezier(.18,.76,.2,1)',fill:'forwards'});
    effects.add(animation);state.animation=animation;
    animation.finished.then(()=>{effects.delete(animation);papers.delete(paper);paper.remove();if(state.flight===paper)state.flight=null;if(state.animation===animation)state.animation=null;if(departing.get(state.key)===state)departing.delete(state.key);},()=>{effects.delete(animation);papers.delete(paper);paper.remove();if(state.flight===paper)state.flight=null;if(state.animation===animation)state.animation=null;if(departing.get(state.key)===state)departing.delete(state.key);});
  }
  function riskKey(value) {return [value.revision,value.rule_id,value.metric,String(value.year)].join('|');}
  function markerRisk(marker) {return {revision:marker.dataset.sourceRiskRevision,rule_id:marker.dataset.sourceRiskRuleId,metric:marker.dataset.sourceRiskMetric,year:marker.dataset.sourceRiskYear};}
  function reserve(state, enabled) {
    const target=state.prefix?report(state.prefix):state.kind==='risk'?document.querySelector('.st-key-risk_atlas_workspace'):null;
    if (!target) return;
    const className=state.prefix?'rr-dock-open':'qm-risk-dock-open';
    target.classList.toggle(className,enabled&&desktop.matches);
    if(enabled&&desktop.matches)target.style.setProperty('--qm-source-reserve',Math.min(430,innerWidth*.37)+38+'px');
    else target.style.removeProperty('--qm-source-reserve');
  }
  function takePrepared(marker) {
    const key=marker.dataset.sourceDockReportPrefix+'|'+marker.dataset.sourceDockReference,pending=prepared.get(key);
    prepared.delete(key);
    return pending&&performance.now()-pending.started < 12000?pending:null;
  }
  function originFor(marker) {
    const prefix=marker.dataset.sourceDockReportPrefix,pending=takePrepared(marker);
    if(pending)return pending;
    if(marker.dataset.sourceDockKind==='risk')return {box:riskOrigins.get(riskKey(markerRisk(marker)))?.box||null};
    const element=document.getElementById(marker.dataset.sourceDockOrigin);
    return {box:box(element),origin:descriptor(element,prefix),reading:captureReading(prefix,null)};
  }
  function scan() {
    frame=0;if(disposed)return;
    const fresh=new Map();
    document.querySelectorAll('[data-source-dock]').forEach(marker=>{const panel=panelFor(marker);if(panel)fresh.set(marker.dataset.sourceDock,{marker,panel});});
    for(const [key,state] of mounted)if(!fresh.has(key)){
      const from=stopFlight(state)||state.box;
      const reading=state.closingReading||captureReading(state.prefix,state.origin);
      reserve(state,false);mounted.delete(key);
      const target=findAnchor(state.origin);
      if(state.prefix&&report(state.prefix)){compensate(reading);restoreReading(reading);target?.focus?.({preventScroll:true});}
      const to=box(target)||state.originBox;
      if(state.kind==='risk'||target){departing.set(key,state);flight(state,from,to,true);if(!state.flight)departing.delete(key);}
    }
    for(const [key,item] of fresh){
      const {marker,panel}=item,identity=marker.dataset.sourceDockIdentity;
      const prior=mounted.get(key);
      if(prior&&prior.identity===identity){
        prior.marker=marker;prior.panel=panel;prior.box=box(panel);
        const pending=takePrepared(marker);if(pending){prior.origin=pending.origin;prior.originBox=pending.box;}
        reserve(prior,true);continue;
      }
      const origin=originFor(marker),returning=departing.get(key);
      if(returning){origin.box=stopFlight(returning)||origin.box;departing.delete(key);}
      const state={key,marker,panel,identity,kind:marker.dataset.sourceDockKind,prefix:marker.dataset.sourceDockReportPrefix,
        origin:origin.origin,originBox:origin.box,closingReading:null,box:box(panel),flight:null};
      if(prior){stopFlight(prior);reserve(prior,false);}
      mounted.set(key,state);reserve(state,true);
      state.box=box(panel);
      if(desktop.matches){restoreReading(origin.reading);flight(state,origin.box,state.box);}
      else panel.scrollIntoView({behavior:reduced.matches?'auto':'smooth',block:'start'});
    }
  }
  function refresh(){if(!frame&&!disposed&&!document.hidden)frame=requestAnimationFrame(scan);}
  function closeButton(state){return state.panel.querySelector(selector(state.marker.dataset.sourceDockClose)+' button');}
  function rememberClose(state){state.closingReading=captureReading(state.prefix,state.origin);if(state.flight)state.box=box(state.flight)||state.box;}
  document.addEventListener('click',event=>{
    const button=event.target.closest?.('button');
    for(const state of mounted.values())if(button&&button===closeButton(state)){rememberClose(state);break;}
  },{capture:true,passive:true,signal:abort.signal});
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape'||event.defaultPrevented||event.isComposing||event.target.closest?.('[role="listbox"],[role="dialog"]'))return;
    const states=[...mounted.values()],state=states[states.length-1],button=state&&closeButton(state);
    if(!button||button.disabled)return;
    event.preventDefault();rememberClose(state);button.click();
  },{signal:abort.signal});
  window.addEventListener('message',event=>{
    const data=event.data;
    if(data?.type!=='qm:risk-source-anchor'||data.version!==1||typeof data.revision!=='string'||!/^R0[1-6]$/.test(data.rule_id)||typeof data.metric!=='string'||!Number.isInteger(data.year))return;
    const iframe=[...document.querySelectorAll('iframe')].find(node=>node.contentWindow===event.source&&/qm_risk_atlas(?:\/|\?|$)/.test(node.getAttribute('src')||''));
    const outer=box(iframe),rect=data.rect;
    if(!outer||!rect||![rect.left,rect.top,rect.width,rect.height].every(Number.isFinite)||rect.left < 0||rect.top < 0||rect.width <= 0||rect.height <= 0||rect.left+rect.width > outer.width+2||rect.top+rect.height > outer.height+2)return;
    const record={box:{left:outer.left+rect.left,top:outer.top+rect.top,width:rect.width,height:rect.height},started:performance.now()};
    const key=riskKey(data);riskOrigins.set(key,record);
    if(riskOrigins.size > 12)riskOrigins.delete(riskOrigins.keys().next().value);
    for(const state of mounted.values())if(state.kind==='risk'&&riskKey(markerRisk(state.marker))===key)state.originBox=record.box;
  },{signal:abort.signal});
  const mutation=new MutationObserver(refresh);mutation.observe(document.body,{childList:true,subtree:true});
  const resize=new ResizeObserver(refresh);
  document.querySelectorAll('[data-testid="stMain"]').forEach(node=>resize.observe(node));
  function layoutChanged(){cancelVisuals();cancelRestore();for(const state of mounted.values())reserve(state,true);refresh();}
  desktop.addEventListener('change',layoutChanged,{signal:abort.signal});
  reduced.addEventListener('change',()=>{cancelVisuals();refresh();},{signal:abort.signal});
  window.addEventListener('resize',layoutChanged,{passive:true,signal:abort.signal});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelVisuals();cancelRestore();if(frame)cancelAnimationFrame(frame);frame=0;}else refresh();},{signal:abort.signal});
  const api={version:VERSION,prepare,refresh,dispose(){
    if(disposed)return;disposed=true;abort.abort();mutation.disconnect();resize.disconnect();
    if(frame)cancelAnimationFrame(frame);frame=0;cancelRestore();cancelVisuals();for(const state of mounted.values())reserve(state,false);
    mounted.clear();departing.clear();prepared.clear();riskOrigins.clear();delete html.dataset.qmSourceDock;
    if(window.__qmSourceDock===api)delete window.__qmSourceDock;
  }};
  window.__qmSourceDock=api;refresh();
})();
