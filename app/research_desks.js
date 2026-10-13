/* .19: one bounded controller owns only explicitly marked decorative layers. */
(function(win){
 'use strict';
 const VERSION='2026-10-11.19-document-ready',doc=win.document,ROOT='[data-desk-scene][data-desk-id]';
 if(win.QMResearchDesks?.version===VERSION){win.QMResearchDesks.refresh();return;}
 win.QMResearchDesks?.dispose();
 const records=new Map(),seen=new Set(),abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
 let frame=0,disposed=false;
 const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
 const visible=node=>{const box=node.getBoundingClientRect();return box.width>0&&box.height>0&&box.bottom>0&&box.top<(win.innerHeight||900);};
 function remember(key){seen.add(key);if(seen.size>256)seen.delete(seen.values().next().value);}
 function settle(record){record.timeline?.kill();record.timeline=null;record.pose.progress=1;record.node.style.setProperty('--desk-progress','1');}
 function enter(record){
   if(record.entered||!record.visible)return;
   record.entered=true;remember(record.key);
   if(quiet()||!win.gsap?.timeline){settle(record);return;}
   record.pose.progress=0;record.node.style.setProperty('--desk-progress','0');
   record.timeline=win.gsap.timeline({defaults:{ease:'power3.out'}}).to(record.pose,{progress:1,duration:record.node.dataset.deskScene==='import'?1.05:.82,onUpdate:()=>record.node.style.setProperty('--desk-progress',String(record.pose.progress)),onComplete:()=>{record.timeline=null;}});
 }
 function forget(record){record.timeline?.kill();intersection?.unobserve(record.node);record.node.style.removeProperty('--desk-progress');records.delete(record.node);}
 function scan(){
   frame=0;if(disposed||!doc.body)return;
   for(const record of [...records.values()])if(!record.node.isConnected)forget(record);
   for(const node of doc.querySelectorAll(ROOT)){
     if(records.has(node)||node.closest('[data-qm-visual-exit]'))continue;
     const key=node.dataset.deskScene+':'+node.dataset.deskId;
     const record={node,key,pose:{progress:1},visible:visible(node),entered:seen.has(key),timeline:null};
     records.set(node,record);intersection?.observe(node);enter(record);
   }
 }
 function schedule(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
 const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{for(const entry of entries){const record=records.get(entry.target);if(!record)continue;record.visible=entry.isIntersecting;if(record.visible)enter(record);else if(record.entered)settle(record);}},{threshold:0}):null;
 const mutations=new win.MutationObserver(changes=>{if(changes.some(change=>[...change.addedNodes,...change.removedNodes].some(node=>node instanceof win.Element&&(node.matches(ROOT)||node.querySelector(ROOT)))))schedule();});
 // Trusted scripts may run from <head> before body exists; Document is stable
 // through both initial body creation and native body replacement.
 mutations.observe(doc,{childList:true,subtree:true});
 function mode(){for(const record of records.values())if(quiet())settle(record);else enter(record);}
 function dispose(){if(disposed)return;disposed=true;if(frame)win.cancelAnimationFrame(frame);mutations.disconnect();intersection?.disconnect();for(const record of [...records.values()])forget(record);seen.clear();abort.abort();media.removeEventListener('change',mode);}
 doc.addEventListener('visibilitychange',mode,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});media.addEventListener('change',mode);
 // Inline evidence is not registered with the overlay drawer controller.
 // Escape invokes the same native close action and never submits a form.
 doc.addEventListener('keydown',event=>{
   if(event.key!=='Escape'||event.defaultPrevented||doc.querySelector('[role="listbox"],[role="dialog"]'))return;
   const panel=doc.querySelector('[class*="st-key-answer_sources_inline_"]');
   if(panel&&(panel.contains(doc.activeElement)||doc.activeElement?.closest('[class*="st-key-answer_sources_toggle_"]'))){
     const close=panel.querySelector('[class*="st-key-answer_sources_close_"] button');
     if(close){event.preventDefault();close.click();}
   }
 },{signal:abort.signal});
 win.QMResearchDesks={version:VERSION,refresh:schedule,dispose};scan();
})(window);
