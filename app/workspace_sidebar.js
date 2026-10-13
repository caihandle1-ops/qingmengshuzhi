/* Only inert rules and paper shapes animate; native controls remain stationary. */
(function(win){
  'use strict';
  const VERSION='2026-10-11.20-sidebar-settings',doc=win.document,SELECTOR='[data-sidebar-reveal][data-sidebar-reveal-id]';
  if(win.QMWorkspaceSidebar?.version===VERSION&&!win.QMWorkspaceSidebar.disposed){win.QMWorkspaceSidebar.refresh();return;}
  win.QMWorkspaceSidebar?.dispose();
  const records=new Map(),seen=new Set(),abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
  let disposed=false,frame=0;
  const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
  const visible=node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<(win.innerHeight||900);};
  function paint(record){record.node.style.setProperty('--sidebar-reveal',String(record.pose.line));record.node.style.setProperty('--settings-reveal',String(record.pose.paper));}
  function settle(record){record.timeline?.kill();record.timeline=null;record.pose.line=record.pose.paper=1;paint(record);}
  function enter(record){
    if(record.entered||!record.visible)return;
    record.entered=true;seen.add(record.key);
    if(seen.size>120)seen.delete(seen.values().next().value);
    if(quiet()||typeof win.gsap?.timeline!=='function'){settle(record);return;}
    record.pose.line=0;record.pose.paper=0;paint(record);
    record.timeline=win.gsap.timeline({defaults:{duration:.65,ease:'power3.out'},onUpdate:()=>paint(record),onComplete:()=>{record.timeline=null;}})
      .addLabel('open',0).to(record.pose,{line:1},'open').to(record.pose,{paper:1,duration:.8},'open+=.08');
  }
  function forget(record){settle(record);intersection?.unobserve(record.node);record.node.style.removeProperty('--sidebar-reveal');record.node.style.removeProperty('--settings-reveal');records.delete(record.node);}
  function scan(){
    frame=0;if(disposed||!doc.body)return;
    for(const record of [...records.values()])if(!record.node.isConnected)forget(record);
    for(const node of doc.querySelectorAll(SELECTOR)){
      if(records.has(node)||node.closest('[data-qm-visual-exit]'))continue;
      if(!['history','settings'].includes(node.dataset.sidebarReveal))continue;
      const key=node.dataset.sidebarReveal+':'+node.dataset.sidebarRevealId;
      const record={node,key,pose:{line:1,paper:1},timeline:null,visible:visible(node),entered:seen.has(key)};
      records.set(node,record);intersection?.observe(node);paint(record);enter(record);
    }
  }
  function schedule(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
  const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{
    for(const entry of entries){const record=records.get(entry.target);if(!record)continue;record.visible=entry.isIntersecting;if(record.visible)enter(record);else settle(record);}
  },{threshold:0}):null;
  const mutations=new win.MutationObserver(changes=>{
    if(changes.some(change=>[...change.addedNodes,...change.removedNodes].some(node=>node instanceof win.Element&&(node.matches(SELECTOR)||node.querySelector(SELECTOR)))))schedule();
  });
  mutations.observe(doc,{childList:true,subtree:true});
  function mode(){for(const record of records.values())if(quiet())settle(record);}
  function dispose(){if(disposed)return;disposed=true;if(frame)win.cancelAnimationFrame(frame);mutations.disconnect();intersection?.disconnect();for(const record of [...records.values()])forget(record);seen.clear();abort.abort();media.removeEventListener('change',mode);}
  doc.addEventListener('visibilitychange',mode,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});win.addEventListener('pagehide',dispose,{signal:abort.signal});media.addEventListener('change',mode);
  win.QMWorkspaceSidebar={version:VERSION,get disposed(){return disposed;},refresh:schedule,dispose,getState:()=>({records:records.size,seen:seen.size,running:[...records.values()].filter(record=>record.timeline).length})};
  schedule();
})(window);
