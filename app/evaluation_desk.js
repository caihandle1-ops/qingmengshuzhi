/* Recorded benchmark marks only. Native data and controls keep their final pose. */
(function(win){
 'use strict';
 const VERSION='2026-10-11.20',doc=win.document,ROOT='[data-evaluation-scene][data-evaluation-id]';
 if(win.QMEvaluationDesk?.version===VERSION&&!win.QMEvaluationDesk.disposed){win.QMEvaluationDesk.refresh();return;}
 win.QMEvaluationDesk?.dispose();
 const records=new Map(),seen=new Set(),abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
 let frame=0,disposed=false;
 const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
 function stop(record){record.timeline?.kill();record.timeline=null;record.node.style.setProperty('--evaluation-reveal','1');}
 function enter(record){
  if(record.entered||!record.visible)return;
  record.entered=true;seen.add(record.key);if(seen.size>160)seen.delete(seen.values().next().value);
  if(quiet()||!win.gsap?.timeline){stop(record);return;}
  record.pose.reveal=0;record.node.style.setProperty('--evaluation-reveal','0');
  record.timeline=win.gsap.timeline({defaults:{ease:'power3.out'}}).addLabel('record')
   .to(record.pose,{reveal:1,duration:.9,onUpdate:()=>record.node.style.setProperty('--evaluation-reveal',String(record.pose.reveal)),onComplete:()=>{record.timeline=null;}},'record');
 }
 function forget(record){record.timeline?.kill();intersection?.unobserve(record.node);record.node.style.removeProperty('--evaluation-reveal');records.delete(record.node);}
 function scan(){
  frame=0;if(disposed||!doc.body)return;
  for(const record of [...records.values()])if(!record.node.isConnected)forget(record);
  for(const node of doc.querySelectorAll(ROOT)){
   if(records.has(node)||node.closest('[data-qm-visual-exit]'))continue;
   const box=node.getBoundingClientRect(),key=node.dataset.evaluationScene+':'+node.dataset.evaluationId;
   const record={node,key,pose:{reveal:1},visible:box.width>0&&box.height>0&&box.bottom>0&&box.top<(win.innerHeight||900),entered:seen.has(key),timeline:null};
   records.set(node,record);intersection?.observe(node);enter(record);
  }
 }
 function refresh(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
 const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{for(const entry of entries){const record=records.get(entry.target);if(!record)continue;record.visible=entry.isIntersecting;if(record.visible)enter(record);else if(record.entered)stop(record);}},{threshold:0}):null;
 const mutation=new win.MutationObserver(changes=>{if(changes.some(change=>[...change.addedNodes,...change.removedNodes].some(node=>node instanceof win.Element&&(node.matches(ROOT)||node.querySelector(ROOT)))))refresh();});
 mutation.observe(doc,{childList:true,subtree:true});
 function mode(){for(const record of records.values())if(quiet())stop(record);else enter(record);}
 function dispose(){if(disposed)return;disposed=true;if(frame)win.cancelAnimationFrame(frame);mutation.disconnect();intersection?.disconnect();for(const record of [...records.values()])forget(record);abort.abort();media.removeEventListener('change',mode);seen.clear();}
 doc.addEventListener('visibilitychange',mode,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});win.addEventListener('pagehide',dispose,{signal:abort.signal});media.addEventListener('change',mode);
 win.QMEvaluationDesk={version:VERSION,refresh,dispose,get disposed(){return disposed;}};refresh();
})(window);
