/* Real authorized original pixels/text; only the aperture is animated. */
(function(win){
 'use strict';const VERSION='20261009.13-lens-body-ready20',doc=win.document;
 if(win.QMEvidenceLens?.version===VERSION){win.QMEvidenceLens.refresh();return;}win.QMEvidenceLens?.dispose();
 const abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)'),colors=win.matchMedia('(forced-colors: active)');
 const mounted=new Map(),saved=new Map();let frame=0,disposed=false;
 const quiet=()=>media.matches||colors.matches||doc.documentElement.dataset.qmMotionMode==='research';
 function paint(record){
  const p=record.pose;record.cover.style.setProperty('--el-x',p.x+'px');record.cover.style.setProperty('--el-y',p.y+'px');record.cover.style.setProperty('--el-radius',p.radius+'px');
  record.rim.style.transform='translate('+(p.x-82)+'px,'+(p.y-82)+'px)';record.rim.style.opacity=String(p.rim);
 }
 function measure(record){record.bounds=record.surface.getBoundingClientRect();return record.bounds.width>0&&record.bounds.height>0;}
 function settle(record,opened){record.transition?.pause().kill();record.transition=null;record.qx.tween.pause();record.qy.tween.pause();record.opened=opened;if(!opened){record.pose.radius=82;record.pose.rim=1;paint(record);}record.node.dataset.elOpen=String(opened);record.node.dataset.elQuiet=String(quiet());record.button.disabled=quiet();record.button.setAttribute('aria-expanded',String(opened));record.button.textContent=opened?'收拢透镜 ↙':'展开原文 ↗';record.surface.setAttribute('aria-label',opened?'引用原件浏览':'移动指针透视原件，点击展开原文');}
 function toggle(record,opened){
  if(quiet()){settle(record,true);return;}
  record.userOpened=opened;saved.set(record.id,opened);if(saved.size>24)saved.delete(saved.keys().next().value);
  if(doc.hidden||!measure(record)){settle(record,opened);return;}
  const wasFullyOpen=record.node.dataset.elOpen==='true';
  record.transition?.kill();record.qx.tween.pause();record.qy.tween.pause();
  record.node.dataset.elOpen='false';record.surface.scrollTop=0;
  const radius=Math.hypot(record.bounds.width,record.bounds.height)*1.1;
  if(!opened && wasFullyOpen){record.pose.radius=radius;record.pose.rim=0;}
  record.context.add(()=>{record.transition=win.gsap.to(record.pose,{radius:opened?radius:82,rim:opened?0:1,duration:opened?.85:.7,ease:'power3.inOut',onUpdate:()=>paint(record),onComplete:()=>settle(record,opened)});});
 }
 function mount(node){
  if(mounted.has(node)||!win.gsap?.quickTo)return;
  const surface=node.querySelector('[data-el-surface]'),cover=node.querySelector('[data-el-cover]'),rim=node.querySelector('[data-el-rim]'),button=node.querySelector('[data-el-toggle]');
  if(!surface||!cover||!rim||!button)return;
  const record={id:node.dataset.evidenceLens,node,surface,cover,rim,button,abort:new win.AbortController(),pose:{x:300,y:180,radius:82,rim:1}};
  mounted.set(node,record);record.context=win.gsap.context(()=>{},node);
  record.context.add(()=>{record.qx=win.gsap.quickTo(record.pose,'x',{duration:.3,ease:'power2.out',onUpdate:()=>paint(record)});record.qy=win.gsap.quickTo(record.pose,'y',{duration:.3,ease:'power2.out',onUpdate:()=>paint(record)});});
  measure(record);record.pose.x=record.bounds.width*.72;record.pose.y=record.bounds.height*.53;paint(record);
  record.userOpened=saved.get(record.id)??false;node.dataset.elReady='true';settle(record,quiet()||record.userOpened);
  const options={signal:record.abort.signal};surface.tabIndex=0;surface.setAttribute('role','group');
  surface.addEventListener('pointerenter',()=>measure(record),options);
  surface.addEventListener('pointermove',event=>{if(record.opened||record.transition?.isActive()||quiet()||doc.hidden||event.pointerType==='touch')return;const b=record.bounds;record.qx(Math.max(30,Math.min(b.width-30,event.clientX-b.left)));record.qy(Math.max(30,Math.min(b.height-30,event.clientY-b.top)));},options);
  surface.addEventListener('click',()=>{if(!record.userOpened)toggle(record,true);},options);
  surface.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle(record,!record.userOpened);}else if(event.key==='Escape'&&record.opened){event.preventDefault();toggle(record,false);}},options);
  button.addEventListener('click',()=>toggle(record,!record.userOpened),options);
 }
 function unmount(record){record.abort.abort();record.transition?.kill();record.context.revert();delete record.node.dataset.elReady;delete record.node.dataset.elOpen;delete record.node.dataset.elQuiet;record.button.disabled=false;record.surface.removeAttribute('tabindex');record.surface.removeAttribute('role');record.surface.removeAttribute('aria-label');mounted.delete(record.node);}
 function scan(){frame=0;for(const record of mounted.values())if(!record.node.isConnected)unmount(record);doc.querySelectorAll('[data-evidence-lens]').forEach(mount);}
 function refresh(){if(!frame&&!disposed)frame=win.requestAnimationFrame(scan);}
 function stop(){for(const record of mounted.values())settle(record,quiet()||record.userOpened);}
 const mutation=new win.MutationObserver(refresh);mutation.observe(doc,{childList:true,subtree:true});
 win.addEventListener('resize',()=>{stop();for(const record of mounted.values()){measure(record);record.pose.x=record.bounds.width*.72;record.pose.y=record.bounds.height*.53;paint(record);}},{signal:abort.signal,passive:true});
 doc.addEventListener('visibilitychange',stop,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',stop,{signal:abort.signal});media.addEventListener('change',stop);colors.addEventListener('change',stop);
 function dispose(){disposed=true;abort.abort();mutation.disconnect();if(frame)win.cancelAnimationFrame(frame);for(const record of [...mounted.values()])unmount(record);saved.clear();media.removeEventListener('change',stop);colors.removeEventListener('change',stop);}
 win.addEventListener('pagehide',dispose,{signal:abort.signal});win.QMEvidenceLens={version:VERSION,refresh,dispose,getState:()=>[...mounted.values()].map(record=>({id:record.id,opened:record.opened,running:Boolean(record.transition?.isActive()||record.qx.tween.isActive()||record.qy.tween.isActive())}))};refresh();
})(window);
