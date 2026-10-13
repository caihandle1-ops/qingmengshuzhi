/* Native navigation owns interaction. GSAP owns only the inert illustrations. */
(function(win){
  'use strict';
  const VERSION='2026-10-11.23-entry-planes',doc=win.document,ROOT='[data-hub-entry][data-hub-kind]';
  if(win.QMVerificationHub?.version===VERSION){win.QMVerificationHub.refresh();return;}
  win.QMVerificationHub?.dispose();
  const keys=new Set(['workspace_feature_0','workspace_feature_1','workspace_feature_2','workspace_enterprise','workspace_library','workspace_evaluation','workspace_system','workspace_agents']);
  const records=new Map(),seen=new Set(),abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
  let disposed=false,frame=0;
  const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
  const visible=node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.right>0&&r.top<(win.innerHeight||900)&&r.left<(win.innerWidth||1600);};
  const enabled=record=>!quiet()&&record.visible&&typeof win.gsap?.to==='function';
  function paint(record){record.art.style.setProperty('--hub-enter',String(record.pose.enter));record.art.style.setProperty('--hub-hover',String(record.pose.hover));}
  function stop(record){record.entrance?.kill();record.response?.kill();record.entrance=record.response=null;}
  function settle(record){stop(record);record.pose.enter=1;record.pose.hover=0;paint(record);}
  function respond(record){
    record.response?.kill();record.response=null;
    const hover=enabled(record)&&!record.button.disabled&&(record.hovered||record.focused)?1:0;
    if(!enabled(record)){record.pose.hover=0;paint(record);return;}
    record.response=win.gsap.to(record.pose,{hover,duration:hover?.7:.38,ease:'power3.out',overwrite:'auto',onUpdate:()=>paint(record),onComplete:()=>{record.response=null;}});
  }
  function enter(record){
    if(record.entered||!record.visible)return;
    record.entered=true;seen.add(record.key);
    if(!enabled(record)){settle(record);return;}
    record.pose.enter=0;paint(record);
    record.entrance=win.gsap.to(record.pose,{enter:1,duration:.9,ease:'power3.out',onUpdate:()=>paint(record),onComplete:()=>{record.entrance=null;}});
  }
  function restoreAttr(node,name,value){if(value===null)node.removeAttribute(name);else node.setAttribute(name,value);}
  function forget(record){
    stop(record);intersection?.unobserve(record.host);records.delete(record.art);
    record.art.style.removeProperty('--hub-enter');record.art.style.removeProperty('--hub-hover');
    restoreAttr(record.host,'data-hub-entry-ready',record.previousReady);
    restoreAttr(record.button,'data-qm-ui-button',record.previousButton);
  }
  function scan(){
    frame=0;if(disposed||!doc.body)return;
    for(const record of [...records.values()])if(!record.art.isConnected||!record.button.isConnected||record.art.closest('[class*="st-key-hub_entry_"]')!==record.host)forget(record);
    for(const art of doc.querySelectorAll(ROOT)){
      if(records.has(art)||art.closest('[data-qm-visual-exit]')||!keys.has(art.dataset.hubEntry))continue;
      const key=art.dataset.hubEntry,host=art.closest('.st-key-hub_entry_'+key),button=host?.querySelector('.st-key-'+key+' button');
      if(!host||!button)continue;
      const record={art,host,button,key,pose:{enter:1,hover:0},visible:visible(host),entered:seen.has(key),hovered:false,focused:button===doc.activeElement,
        previousReady:host.getAttribute('data-hub-entry-ready'),previousButton:button.getAttribute('data-qm-ui-button'),entrance:null,response:null};
      // The existing generic sheen/ripple yields to this explicitly scoped owner.
      host.setAttribute('data-hub-entry-ready','true');button.setAttribute('data-qm-ui-button','true');
      const oldRevealHost=host.closest('.st-key-workspace_verification_choices,.st-key-workspace_research_tools');
      if(oldRevealHost)win.__qingmengMotion?.claim(oldRevealHost);
      records.set(art,record);paint(record);intersection?.observe(host);enter(record);respond(record);
    }
  }
  function schedule(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
  function eventRecord(event){if(!(event.target instanceof win.Element))return null;const host=event.target.closest('[class*="st-key-hub_entry_"]');return host?[...records.values()].find(record=>record.host===host):null;}
  function pointer(event,hovered){
    const record=eventRecord(event);if(!record||event.pointerType==='touch'||(event.relatedTarget instanceof win.Node&&record.host.contains(event.relatedTarget)))return;
    record.hovered=hovered;respond(record);
  }
  function focus(event,focused){const record=eventRecord(event);if(record&&event.target===record.button){record.focused=focused;respond(record);}}
  const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{
    for(const entry of entries){const record=[...records.values()].find(item=>item.host===entry.target);if(!record)continue;record.visible=entry.isIntersecting;
      if(record.visible){enter(record);respond(record);}else{record.hovered=false;settle(record);}}
  },{threshold:0}):null;
  const mutations=new win.MutationObserver(changes=>{
    if(changes.some(change=>[...change.addedNodes,...change.removedNodes].some(node=>node instanceof win.Element&&(node.matches(ROOT)||node.querySelector(ROOT)))||change.target instanceof win.Element&&change.target.closest('[class*="st-key-hub_entry_"]')))schedule();
  });
  // Observe the stable Document even when a head-injected script precedes body.
  mutations.observe(doc,{childList:true,subtree:true});
  function mode(){for(const record of records.values()){if(quiet()){record.hovered=false;settle(record);}else{enter(record);respond(record);}}}
  function dispose(){if(disposed)return;disposed=true;if(frame)win.cancelAnimationFrame(frame);mutations.disconnect();intersection?.disconnect();for(const record of [...records.values()])forget(record);seen.clear();abort.abort();media.removeEventListener('change',mode);}
  doc.addEventListener('pointerover',event=>pointer(event,true),{signal:abort.signal,passive:true});
  doc.addEventListener('pointerout',event=>pointer(event,false),{signal:abort.signal,passive:true});
  doc.addEventListener('focusin',event=>focus(event,true),{signal:abort.signal});doc.addEventListener('focusout',event=>focus(event,false),{signal:abort.signal});
  doc.addEventListener('visibilitychange',mode,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});
  win.addEventListener('pagehide',dispose,{signal:abort.signal});media.addEventListener('change',mode);
  win.QMVerificationHub={version:VERSION,refresh:schedule,dispose,getState:()=>({entries:records.size,running:[...records.values()].filter(record=>record.entrance||record.response).length})};
  schedule();
})(window);
