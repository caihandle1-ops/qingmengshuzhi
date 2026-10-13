/* Presentation only. Never emits financial actions or copies original documents. */
(() => {
  'use strict';
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  const VERSION='2026-10-05.3-global-2-body-ready20',selector='[class*="st-key-answer_sources_panel_"]';
  if(window.__qmEvidenceStage?.version===VERSION){window.__qmEvidenceStage.refresh();return;}
  window.__qmEvidenceStage?.dispose();
  const abort=new AbortController(),reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const records=new Map(),intents=new Map(),effects=new Set(),decorations=new Set();
  const root=document.documentElement;
  let frame=0,veil=null,disposed=false,lastRoute=null;
  const enabled=()=>!disposed&&!quiet()&&!document.hidden;
  const panelKey=panel=>Array.from(panel?.classList||[]).find(value=>value.startsWith('st-key-answer_sources_panel_'));
  const keyed=(node,prefix)=>Array.from(node?.classList||[]).find(value=>value.startsWith(prefix));
  const find=key=>key?document.querySelector('.'+CSS.escape(key)):null;
  const box=node=>node?.isConnected?rect(node.getBoundingClientRect()):null;
  function rect(value){if(!value||!['left','top','width','height'].every(key=>Number.isFinite(value[key])))return null;if(value.width<=0||value.height<=0||value.width>16000||value.height>16000||Math.abs(value.left)>32000||Math.abs(value.top)>32000)return null;return {left:value.left,top:value.top,width:value.width,height:value.height};}
  function visible(value){return value&&value.left+value.width>0&&value.top+value.height>0&&value.left < innerWidth&&value.top < innerHeight;}
  const owns=panel=>Boolean(panelKey(panel));
  function effect(node,frames,options,record){if(!enabled()||!node?.animate)return null;const animation=node.animate(frames,options);effects.add(animation);record?.effects.add(animation);animation.finished.catch(()=>{}).finally(()=>{effects.delete(animation);record?.effects.delete(animation);});return animation;}
  function clearEffect(record){for(const animation of record.effects)animation.cancel();record.effects.clear();if(record.deck){record.deck.remove();decorations.delete(record.deck);record.deck=null;}}
  function shade(){if(veil?.isConnected)return;veil=document.createElement('div');veil.className='qm-evidence-veil';veil.setAttribute('aria-hidden','true');document.body.appendChild(veil);decorations.add(veil);effect(veil,[{opacity:0},{opacity:1}],{duration:620,easing:'ease-out'});}
  function unshade(){if(!veil)return;veil.remove();decorations.delete(veil);veil=null;}
  function paper(target){const deck=document.createElement('div');deck.className='qm-evidence-deck';deck.setAttribute('aria-hidden','true');deck.setAttribute('data-qm-evidence-visual','true');deck.inert=true;Object.assign(deck.style,{left:target.left+'px',top:target.top+'px',width:target.width+'px',height:target.height+'px'});for(const name of ['qm-evidence-sheet','qm-evidence-sheet','qm-evidence-cover','qm-evidence-fold']){const layer=document.createElement('i');layer.className=name;deck.appendChild(layer);}document.body.appendChild(deck);decorations.add(deck);return deck;}
  function transform(origin,target){return 'translate('+(origin.left-target.left)+'px,'+(origin.top-target.top)+'px) scale('+(origin.width/target.width)+','+(origin.height/target.height)+')';}
  function fallback(panel,key){const button=find(key.replace('answer_sources_panel_','answer_sources_toggle_'))?.querySelector('button');const target=box(panel),candidate=box(button);return {rect:visible(candidate)?candidate:{left:Math.min(innerWidth-54,(target?.left||0)+40),top:Math.max(65,Math.min(innerHeight-54,(target?.top||80)+40)),width:48,height:48},node:button,returnKey:key.replace('answer_sources_panel_','answer_sources_toggle_')};}
  function originFor(record){const current=box(record.anchor.node);return visible(current)?current:visible(record.anchor.rect)?record.anchor.rect:fallback(record.panel,record.key).rect;}
  function open(panel){
    const key=panelKey(panel);if(!key||disposed)return false;
    window.__qingmengMotion?.claim?.(panel);
    let record=records.get(key);
    if(record){const changed=record.panel!==panel;record.panel=panel;if(record.phase==='closing'&&(record.removed||intents.has(key))&&changed){const live=box(record.deck);clearEffect(record);record.removed=false;intents.delete(key);beginOpen(record,live||originFor(record));}return true;}
    const intent=intents.get(key),anchor=intent&&performance.now()-intent.at < 10000?intent:fallback(panel,key);
    intents.delete(key);record={key,panel,anchor,effects:new Set(),deck:null,phase:'open',removed:false,serial:0};records.set(key,record);beginOpen(record,originFor(record));return true;
  }
  function beginOpen(record,origin){
    const target=box(record.panel);if(!target||!enabled()||typeof record.panel.animate!=='function'){clearEffect(record);record.phase='open';root.dataset.qmEvidencePhase='static';return;}
    clearEffect(record);const serial=++record.serial;record.phase='opening';shade();record.deck=paper(target);
    const start=transform(origin,target);root.dataset.qmEvidencePhase='opening';root.dataset.qmEvidenceAnchor=[origin.left,origin.top,origin.width,origin.height].map(value=>value.toFixed(1)).join(',');
    const geometry=effect(record.deck,[{transform:start,opacity:1,borderRadius:'16px',offset:0},{opacity:1,offset:.72},{transform:'translate(0px,0px) scale(1,1)',opacity:0,borderRadius:'6px',offset:1}],{duration:1020,easing:'cubic-bezier(.2,.75,.18,1)',fill:'forwards'},record);
    if(!geometry){clearEffect(record);unshade();record.phase='open';root.dataset.qmEvidencePhase='static';return;}
    for(const [index,sheet] of Array.from(record.deck.children).slice(0,2).entries())effect(sheet,[{transform:'rotate('+(index?22:-16)+'deg) translate('+(index?7:-7)+'%,4%)'},{transform:'rotate(0deg) translate(0,0)'}],{duration:1000,easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'},record);
    effect(record.deck.lastElementChild,[{transform:'rotateY(-72deg)'},{transform:'rotateY(0deg)',opacity:0}],{duration:920,easing:'cubic-bezier(.2,.75,.18,1)',fill:'forwards'},record);
    effect(record.panel,[{opacity:0,offset:0},{opacity:0,offset:.30},{opacity:1,offset:.84},{opacity:1,offset:1}],{duration:1020,easing:'linear',fill:'backwards'},record);
    geometry?.finished.then(()=>{if(record.serial!==serial)return;clearEffect(record);record.phase='open';root.dataset.qmEvidencePhase='open';},()=>{});
  }
  function close(panel){
    const key=panelKey(panel);if(!key)return false;open(panel);const record=records.get(key);if(!record||record.phase==='closing')return true;
    const target=box(panel),live=box(record.deck),origin=originFor(record);clearEffect(record);record.phase='closing';record.removed=false;const serial=++record.serial;
    if(!target||!enabled()||typeof panel.animate!=='function'){record.phase='open';unshade();root.dataset.qmEvidencePhase='static';return true;}
    record.deck=paper(target);root.dataset.qmEvidencePhase='closing';
    const geometry=effect(record.deck,[{transform:live?transform(live,target):'translate(0px,0px) scale(1,1)',opacity:live?1:0,borderRadius:'6px',offset:0},{opacity:1,offset:.18},{transform:transform(origin,target),opacity:0,borderRadius:'16px',offset:1}],{duration:760,easing:'cubic-bezier(.6,0,.18,1)',fill:'forwards'},record);
    if(!geometry){clearEffect(record);unshade();record.phase='open';root.dataset.qmEvidencePhase='static';return true;}
    effect(panel,[{opacity:1},{opacity:0}],{duration:180,easing:'ease-out',fill:'forwards'},record);
    for(const [index,sheet] of Array.from(record.deck.children).slice(0,2).entries())effect(sheet,[{transform:'rotate(0deg)'},{transform:'rotate('+(index?18:-12)+'deg)'}],{duration:760,easing:'ease-in',fill:'forwards'},record);
    geometry?.finished.then(()=>{if(record.serial!==serial)return;clearEffect(record);if(!find(key)){records.delete(key);root.dataset.qmEvidencePhase='closed';}else{record.phase='open';root.dataset.qmEvidencePhase='open';}if(!document.querySelector(selector))unshade();},()=>{});return true;
  }
  function returnKey(panel){const key=panelKey(panel);return records.get(key)?.anchor.returnKey||key?.replace('answer_sources_panel_','answer_sources_toggle_');}
  function remember(key,value){intents.set(key,{...value,at:performance.now()});while(intents.size>32)intents.delete(intents.keys().next().value);}
  document.addEventListener('click',event=>{
    const button=event.target.closest?.('button');if(!button)return;const owner=button.closest('[class*="st-key-"]');
    const name=keyed(owner,'st-key-answer_sources_toggle_')||keyed(owner,'st-key-comparison_source_');
    const closeOwner=keyed(owner,'st-key-answer_sources_close_');
    if(closeOwner){const panel=button.closest(selector);if(panel)close(panel);return;}
    if(!name)return;const key=name.replace(/answer_sources_toggle_|comparison_source_/,'answer_sources_panel_'),panel=find(key);
    if(panel){close(panel);return;}
    const origin=box(button);if(origin)remember(key,{rect:origin,node:button,returnKey:name});
  },{capture:true,passive:true,signal:abort.signal});
  window.addEventListener('message',event=>{
    const data=event.data;if(data?.type!=='qm:evidence-anchor'||data.version!==1||event.origin!==location.origin)return;
    const local=rect(data.rect);if(!local)return;
    const iframe=Array.from(document.querySelectorAll('iframe')).find(candidate=>candidate.contentWindow===event.source);
    if(!iframe)return;let url;try{url=new URL(iframe.src,location.href);}catch{return;}
    if(url.origin!==location.origin||!url.pathname.startsWith('/component/app.research_chart.qm_research_chart/'))return;
    const frameBox=box(iframe);if(!frameBox||local.left < 0||local.top < 0||local.left+local.width>frameBox.width+2||local.top+local.height>frameBox.height+2)return;
    const host=iframe.closest('[class*="st-key-answer_workbench_"]'),hostKey=keyed(host,'st-key-answer_workbench_');if(!hostKey)return;
    const key=hostKey.replace('answer_workbench_','answer_sources_panel_');
    remember(key,{rect:{left:frameBox.left+local.left,top:frameBox.top+local.top,width:local.width,height:local.height},node:null,returnKey:key.replace('answer_sources_panel_','answer_sources_toggle_')});
  },{signal:abort.signal});
  function reset(){for(const record of records.values()){record.serial++;clearEffect(record);record.phase='open';}for(const animation of effects)animation.cancel();effects.clear();for(const node of decorations)node.remove();decorations.clear();veil=null;intents.clear();root.dataset.qmEvidencePhase='static';}
  function scan(){frame=0;if(disposed)return;const header=document.querySelector('[data-studio-location]'),route=header?.getAttribute('data-studio-scene')||header?.getAttribute('data-studio-location');if(lastRoute!==null&&route&&route!==lastRoute)reset();if(route)lastRoute=route;
    for(const panel of document.querySelectorAll(selector))open(panel);
    for(const [key,record] of records){const current=find(key);if(current){record.panel=current;continue;}record.removed=true;if(record.phase!=='closing'){record.serial++;clearEffect(record);records.delete(key);}}
    if(!document.querySelector(selector)&&!Array.from(records.values()).some(record=>record.phase==='closing'))unshade();
  }
  function refresh(){if(!frame&&!disposed)frame=requestAnimationFrame(scan);}
  const observer=new MutationObserver(mutations=>{if(mutations.some(change=>change.type==='attributes'||Array.from(change.addedNodes||[]).concat(Array.from(change.removedNodes||[])).some(node=>node.nodeType===1&&!node.matches?.('.qm-evidence-deck,.qm-evidence-veil'))))refresh();});
  observer.observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['data-studio-location','data-studio-scene']});
  const settle=()=>{reset();refresh();};window.addEventListener('resize',settle,{passive:true,signal:abort.signal});document.addEventListener('visibilitychange',settle,{signal:abort.signal});reduced.addEventListener('change',settle);
  window.addEventListener('qm-motion-preference-change', settle, {signal: abort.signal});
  window.__qmEvidenceStage={version:VERSION,owns,open,close,returnKey,refresh,dispose(){disposed=true;if(frame)cancelAnimationFrame(frame);frame=0;reset();records.clear();observer.disconnect();abort.abort();reduced.removeEventListener('change',settle);}};refresh();
})();
