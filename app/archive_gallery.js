/* Authorised original-page covers; native Streamlit remains the action owner. */
(() => {
  'use strict';
  const VERSION='2026-10-11.19-document-desk-ready';
  if(window.QMArchiveGallery?.version===VERSION&&!window.QMArchiveGallery.disposed){window.QMArchiveGallery.refresh();return;}
  window.QMArchiveGallery?.dispose();window.__qmAssetGallery?.dispose();
  const gsap=window.gsap,abort=new AbortController(),media=window.matchMedia('(prefers-reduced-motion: reduce)');
  const tweens=new Set(),flights=new Set();
  let records=new Map(),model={open:'',selected:''},pending=null,commit='',route=null,frame=0,disposed=false,visible=true,observed=null,deskBefore=null,phase='idle';
  const host=()=>document.querySelector('.st-key-archive_gallery');
  const quiet=()=>media.matches||document.documentElement.dataset.qmMotionMode==='research';
  const enabled=()=>!disposed&&Boolean(gsap?.to)&&!document.hidden&&!quiet()&&visible;
  const currentRoute=()=>document.querySelector('[data-studio-scene]')?.getAttribute('data-studio-scene')||'isolated-archive';
  const bounds=node=>{if(!node?.isConnected)return null;const b=node.getBoundingClientRect();return [b.left,b.top,b.width,b.height].every(Number.isFinite)&&b.width>0&&b.height>0?{left:b.left,top:b.top,width:b.width,height:b.height}:null;};
  const inView=box=>box&&box.left+box.width>0&&box.top+box.height>0&&box.left<innerWidth&&box.top<innerHeight;
  const desk=()=>bounds(host()?.querySelector('[data-archive-desk-face]'));
  function ownedTween(target,from,to){
    if(!enabled()||!target)return null;
    const finish=to.onComplete;
    const options={...to,onComplete(){tweens.delete(tween);finish?.();}};
    const tween=from?gsap.fromTo(target,from,options):gsap.to(target,options);tweens.add(tween);return tween;
  }
  function settle(){
    for(const tween of tweens){tween.progress(1);tween.kill();}tweens.clear();
    for(const flight of flights)flight.remove();flights.clear();
    for(const item of records.values()){
      item.quick?.forEach(fn=>fn.tween.pause());
      if(gsap&&item.parallax)gsap.set(item.parallax,{rotationX:0,rotationY:0,x:0,y:0});
    }
    phase=model.open?'open':'closed';
  }
  function discardRecord(record){record.quick?.forEach(fn=>fn.tween.kill());}
  function collect(){
    const next=new Map();
    for(const node of host()?.querySelectorAll('[data-archive-record]')||[]){
      const id=node.getAttribute('data-archive-record'),box=bounds(node),prior=records.get(id);
      if(!id||!box)continue;
      if(prior?.node===node){next.set(id,{...prior,box,faceBox:bounds(prior.face),baseTransform:prior.volume?getComputedStyle(prior.volume).transform:'none'});continue;}
      const item={node,box,face:node.querySelector('[data-archive-face]'),arrival:node.querySelector('.archive-arrival'),
        parallax:node.querySelector('.archive-parallax'),volume:node.querySelector('.archive-volume')};
      item.faceBox=bounds(item.face);item.baseTransform=item.volume?getComputedStyle(item.volume).transform:'none';
      if(gsap?.quickTo&&item.parallax){item.quick=[gsap.quickTo(item.parallax,'rotationY',{duration:.65,ease:'power3.out'}),gsap.quickTo(item.parallax,'rotationX',{duration:.65,ease:'power3.out'})];}
      next.set(id,item);
    }
    for(const [id,item]of records)if(next.get(id)?.node!==item.node)discardRecord(item);
    return next;
  }
  function travel(item,from,to,opening){
    if(!enabled()||!item?.face||!inView(from)||!inView(to))return;
    const clone=document.createElement('div');clone.className='qm-archive-flight';clone.setAttribute('aria-hidden','true');clone.inert=true;
    const material=getComputedStyle(item.face);
    for(const name of ['--cover','--cover-ink']){const value=material.getPropertyValue(name);if(value)clone.style.setProperty(name,value);}
    // Clone only the server-authored face of this actual current-library file.
    // No generic placeholder and no copied native inputs, IDs or event handlers.
    const face=item.face.cloneNode(true);face.removeAttribute('data-archive-face');face.removeAttribute('class');
    face.style.cssText='width:100%;height:100%;position:relative';clone.append(face);
    Object.assign(clone.style,{left:to.left+'px',top:to.top+'px',width:to.width+'px',height:to.height+'px'});
    document.body.append(clone);flights.add(clone);phase=opening?'extracting':'returning';
    const duration=opening?1.08:.88;
    ownedTween(clone,{x:from.left-to.left,y:from.top-to.top,scaleX:from.width/to.width,scaleY:from.height/to.height,
      rotationY:opening?-16:0,rotationZ:opening?-3:0,opacity:1,transformPerspective:1200},
      {x:0,y:0,scaleX:1,scaleY:1,rotationY:0,rotationZ:0,opacity:0,duration,ease:'power3.inOut',
        onComplete(){clone.remove();flights.delete(clone);phase=model.open?'open':'closed';}});
  }
  function reset(){settle();for(const item of records.values())discardRecord(item);records.clear();pending=null;commit='';model={open:'',selected:''};deskBefore=null;phase='idle';}
  function scan(){
    frame=0;if(disposed||!document.body)return;
    for(const tween of tweens)if(tween.targets().some(target=>target.nodeType&&!target.isConnected)){tween.kill();tweens.delete(tween);}
    const nextRoute=currentRoute();if(route!==null&&nextRoute!==route)reset();route=nextRoute;
    const root=host(),marker=root?.querySelector('[data-archive-commit]');
    if(!root){reset();if(observed)intersection?.unobserve(observed);observed=null;return;}
    if(!marker)return; // Never animate an incomplete native render.
    if(observed!==root){if(observed)intersection?.unobserve(observed);observed=root;intersection?.observe(root);}
    const nextCommit=marker.getAttribute('data-archive-commit'),after=collect();
    if(nextCommit===commit){records=after;if(!pending)deskBefore=desk();return;}
    const first=!commit,before=pending||records,previous=model,previousDesk=deskBefore;pending=null;
    settle();model={open:marker.getAttribute('data-archive-open')||'',selected:marker.getAttribute('data-archive-selected')||''};
    commit=nextCommit;records=after;
    if(enabled()){
      let index=0;
      for(const [id,item]of after){
        if(!inView(item.box))continue;
        const old=before.get(id),delta=old?Math.abs(old.box.left-item.box.left)+Math.abs(old.box.top-item.box.top):0;
        if(!old){ownedTween(item.arrival,{x:first?68:34,y:first?75:28,rotationY:-34,rotationZ:5,opacity:0},
          {x:0,y:0,rotationY:0,rotationZ:0,opacity:1,duration:1.05,delay:Math.min(index++*.1,.3),ease:'power3.out'});}
        else if(delta>1||Math.abs(old.box.width-item.box.width)>1){
          ownedTween(item.arrival,{x:old.box.left-item.box.left,y:old.box.top-item.box.top,
            scaleX:old.box.width/item.box.width,scaleY:old.box.height/item.box.height,transformOrigin:'0 0'},
            {x:0,y:0,scaleX:1,scaleY:1,duration:.85,ease:'power3.inOut',clearProps:'transform,transformOrigin'});
        }
        if(old&&old.baseTransform!==item.baseTransform){ownedTween(item.volume,{transform:old.baseTransform},
          {transform:item.baseTransform,duration:.7,ease:'power3.out',clearProps:'transform'});}
      }
      if(!first&&((model.open&&model.open!==previous.open)||model.selected!==previous.selected)){
        const item=after.get(model.selected)||before.get(model.selected);
        travel(item,before.get(model.selected)?.faceBox||item?.faceBox,desk(),true);
      }
      else if(!first&&previous.open&&!model.open){const item=after.get(previous.open)||before.get(previous.open);travel(item,previousDesk,item?.faceBox,false);}
    }
    if(!flights.size)phase=model.open?'open':'closed';deskBefore=desk();
  }
  function refresh(){if(!disposed&&!frame)frame=requestAnimationFrame(scan);}
  function remember(event){
    if(!event.target.closest?.('.st-key-archive_gallery,.st-key-library_document,.st-key-library_gallery_mode,.st-key-asset_gallery_facets'))return;
    // A native action may cause a rerender. Capture geometry only, and wait for
    // its server-confirmed commit marker before beginning any extraction.
    for(const item of records.values()){item.box=bounds(item.node)||item.box;item.faceBox=bounds(item.face)||item.faceBox;}
    pending=new Map([...records].map(([id,item])=>[id,{...item}]));
    deskBefore=desk();
  }
  function pointer(event){
    if(!enabled()||event.pointerType==='touch')return;
    const owner=event.target.closest?.('[class*="st-key-archive_document_card_"]'),node=owner?.querySelector('[data-archive-record]');
    const item=node&&records.get(node.getAttribute('data-archive-record'));
    if(!item?.quick||!item.box)return;
    const x=Math.max(-1,Math.min(1,(event.clientX-item.box.left)/item.box.width*2-1));
    const y=Math.max(-1,Math.min(1,(event.clientY-item.box.top)/item.box.height*2-1));
    item.quick[0](x*9);item.quick[1](-y*6);
  }
  const intersection=typeof IntersectionObserver==='function'?new IntersectionObserver(entries=>{
    for(const entry of entries)if(entry.target===observed){visible=entry.isIntersecting;if(!visible)settle();else refresh();}
  },{threshold:.02}):null;
  const mutation=new MutationObserver(changes=>{
    if(changes.some(change=>!change.target.closest?.('.qm-archive-flight')&&
      (change.type==='attributes'||[...change.addedNodes,...change.removedNodes].some(node=>node.nodeType===1&&!node.matches?.('.qm-archive-flight')))))refresh();
  });
  // Document survives a head-only bootstrap and later body replacement.
  mutation.observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['data-archive-commit','data-studio-scene']});
  for(const type of ['click','change','input'])document.addEventListener(type,remember,{capture:true,passive:true,signal:abort.signal});
  document.addEventListener('pointermove',pointer,{passive:true,signal:abort.signal});
  document.addEventListener('pointerout',event=>{
    const owner=event.target.closest?.('[class*="st-key-archive_document_card_"]');
    if(!owner||owner.contains(event.relatedTarget))return;
    const id=owner.querySelector('[data-archive-record]')?.getAttribute('data-archive-record');
    records.get(id)?.quick?.forEach(fn=>{if(enabled())fn(0);});
  },{passive:true,signal:abort.signal});
  const preference=()=>{settle();refresh();};
  document.addEventListener('visibilitychange',preference,{signal:abort.signal});
  window.addEventListener('qm-motion-preference-change',preference,{signal:abort.signal});
  window.addEventListener('resize',preference,{passive:true,signal:abort.signal});
  window.addEventListener('scroll',()=>{if(flights.size)settle();},{capture:true,passive:true,signal:abort.signal});
  media.addEventListener('change',preference);
  function dispose(){if(disposed)return;disposed=true;if(frame)cancelAnimationFrame(frame);frame=0;reset();intersection?.disconnect();mutation.disconnect();abort.abort();media.removeEventListener('change',preference);window.removeEventListener('pagehide',dispose);}
  window.addEventListener('pagehide',dispose,{once:true});
  window.QMArchiveGallery={version:VERSION,refresh,dispose,get disposed(){return disposed;},
    getState:()=>({version:VERSION,commit,phase,records:records.size,flights:flights.size,active:tweens.size,route})};
  refresh();
})();
