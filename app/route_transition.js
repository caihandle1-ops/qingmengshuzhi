/* Native navigation owns state. This controller only connects its painted scenes. */
(() => {
  const VERSION='2026-10-05.2';
  if(window.__qmRouteStage?.version===VERSION)return;
  window.__qmRouteStage?.dispose();
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'),abort=new AbortController();
  const effects=new Set(),anchors=new Map();
  let active=null,sequence=0,disposed=false;
  const root=document.documentElement;
  const available=()=>!disposed&&!reduced.matches&&!document.hidden&&typeof root.animate==='function';
  function box(node){const b=node?.getBoundingClientRect?.();return b&&[b.left,b.top,b.width,b.height].every(Number.isFinite)&&b.width>1&&b.height>1?{left:b.left,top:b.top,width:b.width,height:b.height}:null;}
  function animate(node,frames,options){if(!node?.animate)return null;try{const effect=node.animate(frames,options);effects.add(effect);effect.finished.catch(()=>{}).finally(()=>effects.delete(effect));return effect;}catch{return null;}}
  function cancel(){sequence++;if(active){clearTimeout(active.deadline);active.plane.remove();active=null;}for(const effect of effects)effect.cancel();effects.clear();root.dataset.qmRouteStage='idle';}
  function viewportBox(){const main=document.querySelector('[data-testid="stMain"]');const bounds=box(main);const left=Math.max(0,bounds?.left||0);return{left:left+12,top:56,width:Math.max(10,innerWidth-left-24),height:Math.max(10,innerHeight-72)};}
  function transform(from,to){return'translate('+(from.left-to.left)+'px,'+(from.top-to.top)+'px) scale('+(from.width/to.width)+','+(from.height/to.height)+')';}
  function isReturn(name){return /返回|回到|上一层|首层/.test(name);}
  function palette(name){if(/核验|复核|口径/.test(name))return'#304f4a';if(/资产|资料|来源/.test(name))return'#963f22';if(/复演|证据包/.test(name))return'#533a8b';if(/评测/.test(name))return'#344a2e';return'#214dd5';}
  function titleOf(button){const labels=Array.from(button.querySelectorAll?.('[data-testid="stMarkdownContainer"] p')||[]);let text=(labels[0]?.textContent||button.innerText||button.textContent||'研究空间').trim();return text.replace(/[↗→]/g,'').replace(/\s+/g,' ').trim().slice(0,42)||'研究空间';}
  function makePlane(rect,title,color){const plane=document.createElement('div');plane.className='qm-route-stage';plane.setAttribute('aria-hidden','true');plane.setAttribute('data-qm-visual-exit','route');Object.assign(plane.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});plane.style.setProperty('--route-color',color);
    const copy=document.createElement('div');copy.className='qm-route-stage-copy';const label=document.createElement('span');label.className='qm-route-stage-title';label.textContent=title;copy.appendChild(label);plane.appendChild(copy);
    const index=document.createElement('span');index.className='qm-route-stage-index';index.textContent='QINGMENG / RESEARCH';plane.appendChild(index);
    for(const name of ['one','two','three']){const piece=document.createElement('i');piece.className='qm-route-stage-piece '+name;plane.appendChild(piece);}document.body.appendChild(plane);return{plane,label};}
  function begin(button,{back=false,scene=''}={}){
    cancel();if(!available())return false;
    const origin=box(button);if(!origin)return false;
    const name=titleOf(button),destination=viewportBox(),returning=back||isReturn(name);
    const owner=button.closest?.('[class*="st-key-"]');
    const ownerClass=Array.from(owner?.classList||[]).find(value=>value.startsWith('st-key-'))||null;
    const {plane,label}=makePlane(destination,name,palette(name));
    const token=sequence,main=document.querySelector('[data-testid="stMain"]');
    const record={plane,label,token,origin,destination,scene,returning,ownerClass,scroll:main?.scrollTop||0,start:performance.now(),deadline:0};active=record;
    const grow=animate(plane,[{transform:transform(origin,destination),borderRadius:'22px',opacity:.7},{transform:'translate(0px,0px) scale(1,1)',borderRadius:'8px',opacity:1}],{duration:430,easing:'cubic-bezier(.76,0,.24,1)',fill:'both'});
    if(!grow){cancel();return false;}
    record.grow=grow;
    animate(label,[{opacity:0,translate:'0px 42px'},{opacity:1,translate:'0px 0px'}],{duration:440,delay:160,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    record.deadline=setTimeout(()=>{if(active===record){const fade=animate(plane,[{opacity:1},{opacity:0}],{duration:160});if(fade)fade.finished.catch(()=>{}).finally(()=>{if(active===record)cancel();});else cancel();}},1500);
    root.dataset.qmRouteStage='expanding';return true;
  }
  function arrive(target,{location='',previous=''}={}){
    const record=active;if(!record||record.arrived)return false;
    if(!available()||record.scene===location){cancel();return false;}
    record.arrived=true;
    clearTimeout(record.deadline);
    // Remember only the native entry identity and its scroll, never data or files.
    if(!record.returning&&record.ownerClass){anchors.set(location,{parent:previous||record.scene,ownerClass:record.ownerClass,scroll:record.scroll,title:record.label.textContent,color:palette(record.label.textContent)});while(anchors.size>24)anchors.delete(anchors.keys().next().value);}
    let end=box(target),reverse=false;
    const saved=record.returning?anchors.get(previous):null;
    if(saved?.parent===location){
      const selector='.'+CSS.escape(saved.ownerClass);const entry=document.querySelector(selector+' button')||document.querySelector(selector+' label');
      const main=document.querySelector('[data-testid="stMain"]');
      if(entry){if(main)main.scrollTop=saved.scroll;const actual=box(entry);if(actual&&actual.top < innerHeight&&actual.top+actual.height>0){end=actual;reverse=true;record.label.textContent=saved.title;}}
    }
    if(!end){cancel();return false;}
    window.__qingmengMotion?.claim?.(target);
    // A completed native view releases the large plane. Controls never acquire a transform.
    const elapsed=performance.now()-record.start,delay=Math.max(0,430-elapsed),token=record.token;
    const endTransform=transform(end,record.destination);
    const frames=reverse?[{transform:'translate(0px,0px) scale(1,1)',opacity:1,borderRadius:'8px',offset:0},{transform:endTransform,opacity:1,borderRadius:'12px',offset:.84},{transform:endTransform,opacity:0,borderRadius:'12px',offset:1}]:
      [{transform:'translate(0px,0px) scale(1,1)',clipPath:'inset(0 0 0 0)',opacity:1,offset:0},{transform:'translate(0px,0px) scale(1,1)',clipPath:'inset(0 0 82% 0)',opacity:1,offset:.7},{transform:'translate(0px,0px) scale(1,1)',clipPath:'inset(0 0 100% 0)',opacity:0,offset:1}];
    const effect=animate(record.plane,frames,{duration:reverse?680:740,delay,easing:'cubic-bezier(.76,0,.24,1)',fill:'forwards'});
    record.grow?.finished.then(()=>record.grow?.cancel()).catch(()=>{});
    root.dataset.qmRouteStage=reverse?'returning':'revealing';root.dataset.qmRouteStageScene=location;
    if(effect)effect.finished.catch(()=>{}).finally(()=>{if(active===record&&sequence===token)cancel();});else cancel();
    return true;
  }
  const stop=()=>cancel();reduced.addEventListener('change',stop);
  document.addEventListener('visibilitychange',stop,{signal:abort.signal});window.addEventListener('resize',stop,{passive:true,signal:abort.signal});
  window.__qmRouteStage={version:VERSION,begin,arrive,cancel,dispose(){cancel();disposed=true;abort.abort();reduced.removeEventListener('change',stop);anchors.clear();}};
})();
