/* Native navigation owns state. Only this temporary report crosses between views. */
(() => {
  const VERSION='2026-10-11.25-ready-report';
  if(window.__qmRouteStage?.version===VERSION)return;
  window.__qmRouteStage?.dispose();
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'),abort=new AbortController();
  const effects=new Set(),anchors=new Map(),root=document.documentElement;
  let active=null,sequence=0,disposed=false;
  const quiet=()=>reduced.matches||root.dataset.qmMotionMode==='research';
  const available=()=>!disposed&&!quiet()&&!document.hidden&&typeof root.animate==='function';
  function box(node){const b=node?.getBoundingClientRect?.();return b&&[b.left,b.top,b.width,b.height].every(Number.isFinite)&&b.width>1&&b.height>1?{left:b.left,top:b.top,width:b.width,height:b.height}:null;}
  function animate(node,frames,options){if(!node?.animate)return null;try{const effect=node.animate(frames,options);effects.add(effect);effect.finished.catch(()=>{}).finally(()=>effects.delete(effect));return effect;}catch{return null;}}
  function cancel(){sequence++;const record=active;active=null;if(record){clearTimeout(record.deadline);window.QMRouteSignature?.end(record.signature);record.plane.remove();}for(const effect of effects)effect.cancel();effects.clear();root.dataset.qmRouteStage='idle';const cancelled=record?.onCancel;if(record){record.onReveal=null;record.onCancel=null;}cancelled?.();}
  function finishReveal(record,token){
    if(active!==record||sequence!==token)return;
    const revealed=record.onReveal;
    let host=record.arrivalHost;
    if(host?.isConnected===false&&record.arrivalScene)host=document.querySelector('[data-feature-inline="'+CSS.escape(record.arrivalScene)+'"]');
    record.onReveal=null;record.onCancel=null;
    // The native view is ready: release its own report entrance now. The
    // decorative paper keeps flying independently and never gates interaction.
    // No late completion may write to a replacement native view.
    if(host?.isConnected!==false&&host?.dataset)host.dataset.qmRouteArrival='report';
    revealed?.();
  }
  function viewportBox(){const bounds=box(document.querySelector('[data-testid="stMain"]'));const left=Math.max(0,bounds?.left||0);return{left:left+12,top:56,width:Math.max(10,innerWidth-left-24),height:Math.max(10,innerHeight-72)};}
  function transform(from,to,rotation=0){return'translate('+(from.left-to.left)+'px,'+(from.top-to.top)+'px) scale('+(from.width/to.width)+','+(from.height/to.height)+') rotate('+rotation+'deg)';}
  function paperBox(bounds,factor=1){const width=Math.max(1,Math.min(bounds.width,bounds.height/1.31)*factor),height=width*1.31;return{left:bounds.left+(bounds.width-width)/2,top:bounds.top+(bounds.height-height)/2,width,height};}
  function isReturn(name){return /返回|回到|上一层|首层/.test(name);}
  function palette(name){if(/反证/.test(name))return'#792c48';if(/口径|核验|复核/.test(name))return'#244230';if(/资产|资料|来源/.test(name))return'#164d40';if(/复演|证据包/.test(name))return'#533a8b';return'#214dd5';}
  function titleOf(button){const labels=Array.from(button.querySelectorAll?.('[data-testid="stMarkdownContainer"] p')||[]);const text=(labels[0]?.textContent||button.innerText||button.textContent||'研究空间').trim();return text.replace(/[↗→]/g,'').replace(/\s+/g,' ').trim().slice(0,42)||'研究空间';}
  function element(tag,className,text){const node=document.createElement(tag);node.className=className;if(text)node.textContent=text;return node;}
  function makePlane(rect,paper,title,color){
    const plane=element('div','qm-route-stage');plane.setAttribute('aria-hidden','true');plane.setAttribute('data-qm-visual-exit','route');
    Object.assign(plane.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});plane.style.setProperty('--route-color',color);
    const veil=element('div','qm-route-stage-veil');plane.appendChild(veil);
    const report=element('div','qm-route-report');report.setAttribute('data-qm-route-report','');
    Object.assign(report.style,{left:paper.left-rect.left+'px',top:paper.top-rect.top+'px',width:paper.width+'px',height:paper.height+'px'});
    const leaves=[];for(const name of ['far','near']){const leaf=element('i','qm-route-report-leaf '+name);report.appendChild(leaf);leaves.push(leaf);}
    const face=element('div','qm-route-report-face');
    face.appendChild(element('i','qm-route-report-spine'));
    face.appendChild(element('span','qm-route-stage-index','QINGMENG / RESEARCH'));
    const copy=element('div','qm-route-stage-copy'),label=element('span','qm-route-stage-title',title);copy.appendChild(label);face.appendChild(copy);
    const lines=element('div','qm-route-report-lines');for(let index=0;index < 5;index++)lines.appendChild(element('i','qm-route-report-line'));face.appendChild(lines);
    const seal=element('div','qm-route-report-seal');seal.appendChild(element('i',''));seal.appendChild(element('i',''));seal.appendChild(element('i',''));face.appendChild(seal);
    face.appendChild(element('i','qm-route-report-fold'));report.appendChild(face);plane.appendChild(report);document.body.appendChild(plane);
    return{plane,veil,report,face,label,leaves};
  }
  function destinationPaper(target){
    const host=target?.matches?.('[data-feature-inline]')?target:target?.querySelector?.('[data-feature-inline]');
    // The tagged outer SVG group is stable while its animated child is held.
    const object=host?.querySelector?.('[data-qm-route-report-target]');
    const exact=box(object);if(exact&&exact.width>24&&exact.height>32)return{end:paperBox(exact,.96),host};
    const art=box(host)||box(target);if(!art)return{end:null,host};
    const bounds=host?{left:art.left+art.width*.33,top:art.top+art.height*.12,width:art.width*.57,height:art.height*.72}:art;
    return{end:paperBox(bounds,.8),host};
  }
  function begin(button,{back=false,scene=''}={}){
    cancel();if(!available())return false;
    const origin=box(button);if(!origin)return false;
    const name=titleOf(button),destination=viewportBox(),returning=back||isReturn(name);
    const owner=button.closest?.('[class*="st-key-"]'),ownerClass=Array.from(owner?.classList||[]).find(value=>value.startsWith('st-key-'))||null;
    const paper=paperBox({left:destination.left+destination.width*.26,top:destination.top+destination.height*.08,width:destination.width*.56,height:destination.height*.80},.95);
    const startPaper=paperBox(origin,.8);
    // A sidebar entry sends a page in from the content edge, without covering the sidebar.
    startPaper.left=Math.max(destination.left-12,Math.min(startPaper.left,destination.left+destination.width-startPaper.width));
    const nodes=makePlane(destination,paper,name,palette(name)),token=sequence,main=document.querySelector('[data-testid="stMain"]');
    const record={...nodes,token,origin,paper,destination,scene,returning,ownerClass,scroll:main?.scrollTop||0,start:performance.now(),deadline:0};active=record;
    record.signature=window.QMRouteSignature?.begin(record.plane,name);
    const grow=animate(record.report,[{transform:transform(startPaper,paper,-22),opacity:.55},{transform:'translate(0px,0px) scale(1,1) rotate(-7deg)',opacity:1}],{duration:510,easing:'cubic-bezier(.18,.85,.24,1)',fill:'both'});
    if(!grow){cancel();return false;}record.grow=grow;
    animate(record.veil,[{opacity:0},{opacity:1}],{duration:310,easing:'ease-out',fill:'both'});
    animate(record.face,[{transform:'perspective(1100px) rotateY(-48deg)'},{transform:'perspective(1100px) rotateY(0deg)'}],{duration:560,delay:40,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    for(const [index,leaf] of record.leaves.entries())animate(leaf,[{transform:'translate(0px,0px) rotate(0deg)',opacity:0},{transform:'translate('+(index?12:24)+'px,'+(index?-5:-9)+'px) rotate('+(index?5:10)+'deg)',opacity:1}],{duration:540,delay:70+index*45,easing:'cubic-bezier(.16,1,.3,1)',fill:'both'});
    animate(record.label,[{opacity:0,transform:'translateY(24px)'},{opacity:1,transform:'translateY(0px)'}],{duration:360,delay:170,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    record.deadline=setTimeout(()=>{if(active===record){const fade=animate(record.plane,[{opacity:1},{opacity:0}],{duration:180});if(fade)fade.finished.catch(()=>{}).finally(()=>{if(active===record)cancel();});else cancel();}},1700);
    root.dataset.qmRouteStage='expanding';return true;
  }
  function arrive(target,{location='',previous='',onReveal=null,onCancel=null}={}){
    const record=active;if(!record||record.arrived)return false;
    if(!available()||target?.isConnected===false||record.scene===location){cancel();return false;}
    record.arrived=true;record.onReveal=typeof onReveal==='function'?onReveal:null;record.onCancel=typeof onCancel==='function'?onCancel:null;clearTimeout(record.deadline);
    if(!record.returning&&record.ownerClass){anchors.set(location,{parent:previous||record.scene,ownerClass:record.ownerClass,scroll:record.scroll,title:record.label.textContent});while(anchors.size>24)anchors.delete(anchors.keys().next().value);}
    let {end,host}=destinationPaper(target),reverse=false;
    const saved=record.returning?anchors.get(previous):null;
    if(saved?.parent===location){const selector='.'+CSS.escape(saved.ownerClass),entry=document.querySelector(selector+' button')||document.querySelector(selector+' label'),main=document.querySelector('[data-testid="stMain"]');
      if(entry){if(main)main.scrollTop=saved.scroll;const actual=box(entry);if(actual&&actual.top < innerHeight&&actual.top+actual.height>0){end=paperBox(actual,.8);reverse=true;host=null;record.label.textContent=saved.title;}}}
    if(!end){cancel();return false;}record.arrivalHost=host;record.arrivalScene=host?.getAttribute?.('data-feature-inline')||host?.dataset?.featureInline||'';
    window.__qingmengMotion?.claim?.(target);
    window.QMRouteSignature?.land(record.signature,end,record.destination);
    // All geometry has been read before any overlay animation is scheduled.
    // Native buttons, headings, and the destination SVG never acquire transforms here.
    const delay=Math.max(0,510-(performance.now()-record.start)),duration=reverse?620:690,token=record.token,endTransform=transform(end,record.paper,reverse?-10:0);
    const move=animate(record.report,[{transform:'translate(0px,0px) scale(1,1) rotate(-7deg)',opacity:1,offset:0},{transform:endTransform,opacity:1,offset:.88},{transform:endTransform,opacity:reverse||!host?0:1,offset:1}],{duration,delay,easing:'cubic-bezier(.65,0,.2,1)',fill:'forwards'});
    animate(record.veil,[{opacity:1},{opacity:0}],{duration:120,easing:'ease-out',fill:'forwards'});
    for(const leaf of record.leaves)animate(leaf,[{opacity:1},{opacity:0}],{duration:duration*.45,delay:delay+duration*.4,fill:'forwards'});
    record.grow?.finished.then(()=>record.grow?.cancel()).catch(()=>{});
    root.dataset.qmRouteStage=reverse?'returning':'revealing';root.dataset.qmRouteStageScene=location;
    // Keep the full expansion, leaves, signature and landing choreography, but
    // let ready content begin alongside it instead of waiting another 1.2s.
    // Every visual terminal path only cleans up; it cannot release or replay a
    // later native scene. A dropped animation promise also has a bounded exit.
    const finish=()=>{if(active===record&&sequence===token)cancel();};
    if(move){move.finished.then(finish,finish);record.deadline=setTimeout(finish,delay+duration+250);}
    finishReveal(record,token);
    if(!move)finish();
    return true;
  }
  const stop=()=>cancel();reduced.addEventListener('change',stop);
  document.addEventListener('visibilitychange',stop,{signal:abort.signal});window.addEventListener('resize',stop,{passive:true,signal:abort.signal});
  window.addEventListener('qm-motion-preference-change',stop,{signal:abort.signal});
  window.__qmRouteStage={version:VERSION,begin,arrive,cancel,dispose(){cancel();disposed=true;abort.abort();reduced.removeEventListener('change',stop);anchors.clear();}};
})();
