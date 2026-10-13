/* The native buttons own interaction. This controller owns only adjacent art. */
(function(win){
  'use strict';
  const VERSION='2026-10-11.22-entry-planes',doc=win.document,ROOT='[data-tool-entry][data-tool-kind]';
  const ASSETS={asset_import_entry:['align','01 / 接入与复核'],asset_library_entry:['archive','02 / 研究资料库']};
  const ASSET_SELECTOR='.st-key-guided_card_asset_import_entry,.st-key-guided_card_asset_library_entry';
  const hostFor=art=>art.closest('[data-tool-asset],[class*="st-key-tool_entry_"]');
  if(win.QMToolEntries?.version===VERSION){win.QMToolEntries.refresh();return;}
  win.QMToolEntries?.dispose();
  const records=new Map(),seen=new Set(),media=win.matchMedia('(prefers-reduced-motion: reduce)'),abort=new win.AbortController();
  let disposed=false,frame=0;
  const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
  const visible=node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<(win.innerHeight||900);};
  const enabled=record=>!quiet()&&record.visible&&win.gsap?.to;
  function paint(record){record.art.style.setProperty('--tool-enter',String(record.pose.enter));record.art.style.setProperty('--tool-hover',String(record.pose.hover));}
  function stop(record){record.entrance?.kill();record.response?.kill();record.entrance=record.response=null;}
  function settle(record){stop(record);record.pose.enter=1;record.pose.hover=0;paint(record);}
  function feedback(record){
    record.response?.kill();record.response=null;
    const hover=enabled(record)&&!record.button.disabled&&(record.hovered||record.focused)?1:0;
    if(!enabled(record)){record.pose.hover=0;paint(record);return;}
    record.response=win.gsap.to(record.pose,{hover,duration:hover?.65:.42,ease:'power3.out',overwrite:'auto',onUpdate:()=>paint(record),onComplete:()=>{record.response=null;}});
  }
  function enter(record){
    if(record.entered||!record.visible)return;
    record.entered=true;seen.add(record.key);
    if(!enabled(record)){settle(record);return;}
    record.pose.enter=0;paint(record);
    record.entrance=win.gsap.to(record.pose,{enter:1,duration:.95,ease:'power3.out',onUpdate:()=>paint(record),onComplete:()=>{record.entrance=null;}});
  }
  function restoreAttr(node,name,value){if(value===null)node.removeAttribute(name);else node.setAttribute(name,value);}
  function forget(record){
    stop(record);intersection?.unobserve(record.host);records.delete(record.art);
    record.art.style.removeProperty('--tool-enter');record.art.style.removeProperty('--tool-hover');
    restoreAttr(record.host,'data-tool-entry-ready',record.previousReady);
    restoreAttr(record.button,'data-qm-ui-button',record.previousButton);
    if(record.art.dataset.toolInjected==='true'){record.art.remove();record.host.removeAttribute('data-tool-asset');}
  }
  function prepareAssets(){
    for(const [key,[kind,caption]] of Object.entries(ASSETS)){
      for(const host of doc.querySelectorAll('.st-key-guided_card_'+key)){
        if(!host.querySelector('button')||host.querySelector('[data-tool-injected]')||host.closest('[data-qm-visual-exit]'))continue;
        const art=doc.createElement('div');art.className='tool-entry-art tool-entry-art-'+kind;
        art.dataset.toolEntry=key;art.dataset.toolKind=kind;art.dataset.toolInjected='true';art.setAttribute('aria-hidden','true');art.inert=true;
        art.innerHTML='<div class="tool-entry-meta"><span>'+caption+'</span></div><div class="tool-entry-object">'+Array.from({length:6},(_,i)=>'<i class="tool-entry-plane" style="--plane:'+i+'"></i>').join('')+'<i class="tool-entry-axis"></i><i class="tool-entry-orbit"></i></div>';
        host.setAttribute('data-tool-asset',key);host.appendChild(art);
      }
    }
  }
  function scan(){
    frame=0;if(disposed||!doc.body)return;
    for(const record of [...records.values()])if(!record.art.isConnected||!record.button.isConnected||hostFor(record.art)!==record.host)forget(record);
    prepareAssets();
    for(const art of doc.querySelectorAll(ROOT)){
      if(records.has(art)||art.closest('[data-qm-visual-exit]'))continue;
      const key=art.dataset.toolEntry;
      if(!['scope_enter_six','scope_enter_probe','replay_enter_generate','replay_enter_import',...Object.keys(ASSETS)].includes(key))continue;
      const host=hostFor(art),button=ASSETS[key]?host?.querySelector('button'):host?.querySelector('.st-key-'+key+' button');
      if(!host||!button)continue;
      const record={art,host,button,key,pose:{enter:1,hover:0},visible:visible(host),entered:seen.has(key),hovered:false,focused:button===doc.activeElement,
        previousReady:host.getAttribute('data-tool-entry-ready'),previousButton:button.getAttribute('data-qm-ui-button'),entrance:null,response:null};
      // Existing ripple and sheen skip this marker. No listeners synthesize or
      // intercept a click, and no native geometry/style/value is tweened.
      host.setAttribute('data-tool-entry-ready','true');button.setAttribute('data-qm-ui-button','true');
      records.set(art,record);paint(record);intersection?.observe(host);enter(record);feedback(record);
    }
  }
  function schedule(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
  function eventRecord(event){if(!(event.target instanceof win.Element))return null;const host=event.target.closest('[data-tool-asset],[class*="st-key-tool_entry_"]');return host?[...records.values()].find(record=>record.host===host):null;}
  function pointer(event,hovered){
    const record=eventRecord(event);if(!record||event.pointerType==='touch'||(event.relatedTarget instanceof win.Node&&record.host.contains(event.relatedTarget)))return;
    record.hovered=hovered;feedback(record);
  }
  function focus(event,focused){
    const record=eventRecord(event);if(!record||event.target!==record.button)return;
    record.focused=focused;feedback(record);
  }
  const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{
    for(const entry of entries){const record=[...records.values()].find(item=>item.host===entry.target);if(!record)continue;record.visible=entry.isIntersecting;
      if(record.visible){enter(record);feedback(record);}else{record.hovered=false;settle(record);}}
  },{threshold:0}):null;
  const mutations=new win.MutationObserver(changes=>{
    if(changes.some(change=>[...change.addedNodes,...change.removedNodes].some(node=>node instanceof win.Element&&(node.matches(ROOT+','+ASSET_SELECTOR)||node.querySelector(ROOT+','+ASSET_SELECTOR)))||change.target instanceof win.Element&&change.target.closest('[data-tool-asset],[class*="st-key-tool_entry_"]')))schedule();
  });
  mutations.observe(doc,{childList:true,subtree:true});
  function mode(){for(const record of records.values()){if(quiet()){record.hovered=false;settle(record);}else{enter(record);feedback(record);}}}
  function dispose(){if(disposed)return;disposed=true;if(frame)win.cancelAnimationFrame(frame);mutations.disconnect();intersection?.disconnect();for(const record of [...records.values()])forget(record);seen.clear();abort.abort();media.removeEventListener('change',mode);}
  doc.addEventListener('pointerover',event=>pointer(event,true),{signal:abort.signal,passive:true});
  doc.addEventListener('pointerout',event=>pointer(event,false),{signal:abort.signal,passive:true});
  doc.addEventListener('focusin',event=>focus(event,true),{signal:abort.signal});
  doc.addEventListener('focusout',event=>focus(event,false),{signal:abort.signal});
  doc.addEventListener('visibilitychange',mode,{signal:abort.signal});
  win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});
  win.addEventListener('pagehide',dispose,{signal:abort.signal});media.addEventListener('change',mode);
  win.QMToolEntries={version:VERSION,refresh:schedule,dispose,getState:()=>({entries:records.size,running:[...records.values()].filter(record=>record.entrance||record.response).length})};
  schedule();
})(window);
