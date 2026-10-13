/* GSAP draws a route's motif on the transient paper only. No native DOM moves. */
(function(win){
  'use strict';
  const VERSION='2026-10-11.20',doc=win.document;
  if(win.QMRouteSignature?.version===VERSION&&!win.QMRouteSignature.disposed)return;
  win.QMRouteSignature?.dispose();
  const records=new Set(),abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
  let disposed=false;
  const quiet=()=>doc.hidden||media.matches||doc.documentElement.dataset.qmMotionMode==='research';
  function kind(title){if(/口径/.test(title))return'scope';if(/反证|风险/.test(title))return'counter';if(/复演|证据包/.test(title))return'replay';if(/资产|资料|接入/.test(title))return'assets';return'qa';}
  function end(record){if(!record)return;record.timeline?.kill();record.node.remove();records.delete(record);}
  function begin(plane,title){
    if(disposed||quiet()||!win.gsap?.timeline||!plane?.isConnected)return null;
    const type=kind(title),node=doc.createElement('div');node.className='qm-route-signature';
    node.dataset.routeSignature=type;node.setAttribute('aria-hidden','true');node.inert=true;
    const pieces=Array.from({length:type==='scope'?6:type==='replay'?4:3},(_,index)=>{
      const item=doc.createElement('i');item.style.setProperty('--signature-index',index);node.appendChild(item);return item;
    });plane.appendChild(node);
    const record={node,pieces,type,timeline:null,phase:'entry'};records.add(record);
    record.timeline=win.gsap.timeline({defaults:{ease:'power3.out',overwrite:true}})
      .addLabel('unfold',0)
      .fromTo(pieces,{scaleX:.02,opacity:0,x:-60},{scaleX:1,opacity:.65,x:0,duration:.46,stagger:.035},'unfold');
    return record;
  }
  function land(record,endBox,viewport){
    if(!record||!records.has(record))return;
    if(quiet()||!endBox){end(record);return;}
    record.timeline?.kill();record.phase='arrival';
    const dx=(endBox.left+endBox.width/2)-(viewport.left+viewport.width*.72);
    const dy=(endBox.top+endBox.height/2)-(viewport.top+viewport.height*.48);
    record.timeline=win.gsap.timeline({defaults:{ease:'power3.inOut',overwrite:true}})
      .addLabel('connect',0)
      .to(record.node,{x:dx,y:dy,scale:.55,duration:.52},'connect')
      .to(record.pieces,{scaleX:1.2,opacity:.8,duration:.22,stagger:.025},'connect')
      .to(record.node,{opacity:0,duration:.18},'connect+=.38');
  }
  const settle=()=>{for(const record of [...records])end(record);};
  media.addEventListener('change',settle);doc.addEventListener('visibilitychange',settle,{signal:abort.signal});
  win.addEventListener('qm-motion-preference-change',settle,{signal:abort.signal});
  win.QMRouteSignature={version:VERSION,begin,land,end,inspect:()=>({active:records.size}),get disposed(){return disposed;},dispose(){if(disposed)return;disposed=true;settle();abort.abort();media.removeEventListener('change',settle);}};
})(window);
