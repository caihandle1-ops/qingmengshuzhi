/* Native Streamlit owns expansion and data. GSAP Flip carries an inert exact
   text proxy between confirmed layouts; no React node is moved or reparented. */
(function(win){
 'use strict';const VERSION='20261009.13-results-body-ready20',doc=win.document;
 if(win.QMResultContinuity?.version===VERSION){win.QMResultContinuity.refresh();return;}win.QMResultContinuity?.dispose();
 const abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
 const states=new Map(),running=new Map();let pending=null,frame=0,disposed=false;
 const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
 const part=(key,name)=>doc.querySelector('.'+win.CSS.escape('st-key-answer_'+name+'_'+key));
 function rectangle(node){const b=node?.getBoundingClientRect();return b&&[b.left,b.top,b.width,b.height].every(Number.isFinite)&&b.width>1&&b.height>1?b:null;}
 function finish(id){const record=running.get(id);if(!record)return;running.delete(id);record.context.revert();record.proxy.remove();}
 function stop(){pending=null;for(const id of [...running.keys()])finish(id);}
 function nodes(marker){const key=marker.dataset.resultNativeKey;return {lead:part(key,'canvas_lead'),research:part(key,'canvas_research'),button:part(key,'research_toggle')?.querySelector('button')};}
 function capture(marker){
  if(quiet()||!win.Flip||!win.gsap)return;
  const {lead}=nodes(marker),rect=rectangle(running.get(marker.dataset.resultContinuity)?.proxy)||rectangle(lead);if(!rect)return;
  const metric=lead.querySelector('[data-testid="stMetric"]');if(!metric)return;
  pending={id:marker.dataset.resultContinuity,expanded:marker.dataset.resultExpanded,rect,time:performance.now(),
    label:metric.querySelector('[data-testid="stMetricLabel"]')?.textContent||'',
    value:metric.querySelector('[data-testid="stMetricValue"]')?.textContent||'',
    context:[...lead.querySelectorAll('[data-testid="stCaptionContainer"]')].map(node=>node.textContent).join(' · ')};
 }
 function animate(marker,origin){
  const id=marker.dataset.resultContinuity,{lead,research}=nodes(marker),to=rectangle(lead);
  if(!to||quiet()||!win.Flip||!win.gsap)return;
  const from=rectangle(running.get(id)?.proxy)||origin.rect;
  finish(id);win.gsap.registerPlugin(win.Flip);win.__qingmengMotion?.claim?.(lead);win.__qingmengMotion?.claim?.(research);
  const proxy=doc.createElement('div');proxy.className='qm-result-proxy';proxy.inert=true;proxy.setAttribute('aria-hidden','true');proxy.setAttribute('data-qm-visual-exit','result');
  for(const [cls,text] of [['qr-proxy-label',origin.label],['qr-proxy-value',origin.value],['qr-proxy-context',origin.context]]){const item=doc.createElement('p');item.className=cls;item.textContent=text;proxy.appendChild(item);}
  const place=box=>Object.assign(proxy.style,{left:box.left+'px',top:box.top+'px',width:box.width+'px',height:box.height+'px'});
  place(from);doc.body.appendChild(proxy);const state=win.Flip.getState(proxy);place(to);
  const context=win.gsap.context(()=>{},proxy),record={proxy,context,lead};running.set(id,record);
  context.add(()=>{
   win.gsap.set(lead,{opacity:0});
   record.motion=win.Flip.from(state,{duration:.8,scale:true,ease:'power3.inOut',onComplete:()=>finish(id)});
   if(research)win.gsap.fromTo(research,{opacity:.3},{opacity:1,duration:.55,delay:.25,ease:'power2.out'});
  });
 }
 function scan(){frame=0;if(disposed)return;
  const markers=[...doc.querySelectorAll('[data-result-continuity]')],ids=new Set(markers.map(marker=>marker.dataset.resultContinuity));
  for(const id of [...states.keys()])if(!ids.has(id)){states.delete(id);finish(id);}
  for(const marker of markers){
   const id=marker.dataset.resultContinuity,{lead,research,button}=nodes(marker);if(!lead||!research||!button)continue;
   const metric=lead.querySelector('[data-testid="stMetric"]');
   if(metric){metric.setAttribute('role','button');metric.tabIndex=0;metric.setAttribute('aria-expanded',marker.dataset.resultExpanded);metric.setAttribute('aria-label',[button.textContent,metric.querySelector('[data-testid="stMetricLabel"]')?.textContent,metric.querySelector('[data-testid="stMetricValue"]')?.textContent,...[...lead.querySelectorAll('[data-testid="stCaptionContainer"]')].map(node=>node.textContent)].filter(Boolean).join(' · '));}
   const previous=states.get(id);states.set(id,marker.dataset.resultExpanded);
   if(previous!==undefined&&previous!==marker.dataset.resultExpanded&&pending?.id===id&&pending.expanded!==marker.dataset.resultExpanded&&performance.now()-pending.time<12000){const origin=pending;pending=null;animate(marker,origin);}
   const active=running.get(id);if(active&&active.lead!==lead)finish(id);
  }
 }
 function refresh(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
 function markerFor(node){return node.closest?.('[class*="st-key-answer_summary_"]')?.querySelector('[data-result-continuity]');}
 doc.addEventListener('click',event=>{const marker=markerFor(event.target);if(!marker)return;const {lead,button}=nodes(marker);if(event.target.closest('button')===button)capture(marker);else if(lead?.querySelector('[data-testid="stMetric"]')?.contains(event.target)){capture(marker);button?.click();}},{capture:true,signal:abort.signal});
 doc.addEventListener('keydown',event=>{const target=event.target;if(!target.matches?.('[data-testid="stMetric"][role="button"]')||!['Enter',' '].includes(event.key))return;const marker=markerFor(target);if(marker){event.preventDefault();capture(marker);nodes(marker).button?.click();}},{signal:abort.signal});
 const observer=new win.MutationObserver(refresh);observer.observe(doc,{childList:true,subtree:true,attributes:true,attributeFilter:['data-result-expanded']});
 win.addEventListener('resize',stop,{signal:abort.signal,passive:true});doc.addEventListener('visibilitychange',stop,{signal:abort.signal});win.addEventListener('qm-motion-preference-change',stop,{signal:abort.signal});media.addEventListener('change',stop);
 doc.addEventListener('scroll',stop,{capture:true,passive:true,signal:abort.signal});
 function dispose(){disposed=true;stop();abort.abort();observer.disconnect();if(frame)win.cancelAnimationFrame(frame);for(const marker of doc.querySelectorAll('[data-result-continuity]')){const metric=nodes(marker).lead?.querySelector('[data-testid="stMetric"]');if(metric){for(const name of ['role','tabindex','aria-label','aria-expanded'])metric.removeAttribute(name);}}states.clear();media.removeEventListener('change',stop);}
 win.addEventListener('pagehide',dispose,{signal:abort.signal});win.QMResultContinuity={version:VERSION,refresh,dispose,getState:()=>({mounted:states.size,running:running.size,pending:Boolean(pending)})};refresh();
})(window);
