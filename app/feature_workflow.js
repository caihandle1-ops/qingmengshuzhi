/* Editorial feedback is decorative. Values, focus, events and geometry stay native. */
(function(win){
  'use strict';
  const VERSION='2026-10-09.15-workflow-body-ready20',doc=win.document;
  if(win.QMFeatureWorkflow?.version===VERSION)return;
  win.QMFeatureWorkflow?.dispose();
  const media=win.matchMedia('(prefers-reduced-motion: reduce)'),abort=new win.AbortController();
  const running=new Map(),pending=new Map();let disposed=false;
  const quiet=()=>media.matches||doc.hidden||doc.documentElement.dataset.qmMotionMode==='research';
  function finish(stage){
    const record=running.get(stage);if(!record)return;
    running.delete(stage);record.context.revert();
  }
  function settle(){for(const frame of pending.values())win.cancelAnimationFrame(frame);pending.clear();for(const stage of [...running.keys()])finish(stage);}
  function groups(stage){
    const scene=stage.dataset.resultScene;
    let root=stage,selectors;
    if(scene==='qa'){
      root=stage.closest('[class*="st-key-answer_summary_"]')||stage;
      selectors=['.answer-canvas-heading-copy','[data-testid="stMetricValue"]','[class*="st-key-answer_canvas_evidence_"] [data-testid="stMarkdownContainer"] p'];
    }else if(scene==='scope')selectors=['.tr-heading','.tr-scope-records','.tr-scope-values'];
    else if(scene==='counter')selectors=['.tr-heading','.tr-number,.tr-unit','.tr-proof > p,.tr-annotation > span'];
    else if(scene==='replay')selectors=['.tr-heading,.tr-archive-cover h3,.tr-archive-cover p','.tr-folder h4,.tr-replay-values > strong','.tr-folder p,.tr-replay-check > span'];
    else return [];
    return selectors.map(selector=>[...root.querySelectorAll(selector)].filter(node=>!node.matches('input,button,select,textarea')&&!node.querySelector('input,button,select,textarea,[data-result-piece],[data-result-sweep]')));
  }
  function reveal(stage){
    if(disposed||quiet()||!win.gsap||!stage?.isConnected||running.has(stage)||pending.has(stage))return false;
    for(const node of running.keys())if(!node.isConnected)finish(node);
    // React may append metrics after the heading in the same native rerun.
    // Two bounded paints collect them; no polling or extra mutation observer.
    pending.set(stage,win.requestAnimationFrame(()=>{
      pending.set(stage,win.requestAnimationFrame(()=>{
        pending.delete(stage);if(disposed||quiet()||!stage.isConnected)return;
        const phases=groups(stage);if(!phases.some(items=>items.length))return;
        const context=win.gsap.context(()=>{},stage),record={context};running.set(stage,record);
        context.add(()=>{
          record.timeline=win.gsap.timeline({onComplete:()=>finish(stage)});
          phases.forEach((nodes,index)=>{if(nodes.length)record.timeline.fromTo(nodes,{opacity:.45},{opacity:1,duration:.38,stagger:Math.min(.035,.14/nodes.length),ease:'power2.out'},index*.14);});
        });
      }));
    }));return true;
  }
  const composerSelector='.st-key-qa_composer,.st-key-header_search_desktop';
  const groupSelector='.st-key-qa_suggestions,[class*="st-key-guided_picker_"],[class*="st-key-answer_actions_"]';
  // Explicit chrome surfaces only: sidebar routing and paper/evidence readers
  // retain their existing animation owners. Downloads are hover-only controls.
  const surfaceSelector='.st-key-app_header,.st-key-new_session,.st-key-workspace_search_open_button,[class*="st-key-source_document_toolbar_"],[class*="st-key-publication_toolbar_"],[class*="st-key-workspace_search_item_"]';
  const buttonSelector='.st-key-qa_submit button,.st-key-qa_suggestions button,[class*="st-key-guided_picker_"] button,.st-key-layer_navigation button,.st-key-header_search_desktop [data-testid="stFormSubmitButton"] button,.st-key-new_session button,.st-key-workspace_search_open_button button,[class*="st-key-answer_actions_"] button,[class*="st-key-source_document_toolbar_"] button,[class*="st-key-publication_toolbar_"] button,[class*="st-key-workspace_search_item_"] button';
  const disclosureSelector='[data-testid="stMain"] [data-testid="stExpander"] > details > summary';
  const disclosureExcluded='.st-key-qa_composer,.st-key-research_task_strip,.st-key-workspace_hero,[data-testid="stDialog"]';
  const hostSelector=composerSelector+','+groupSelector+','+surfaceSelector;
  // The mutation boundary must also match a detached expander. A selector
  // requiring its former stMain ancestor cannot detect native removal.
  const roots=hostSelector+',[data-testid="stExpander"]';
  const ordinaryDisclosure=node=>node.matches(disclosureSelector)&&!node.closest(disclosureExcluded)&&
    !node.querySelector('[data-testid="stExpanderStepChevron"],[data-testid="stExpanderStepIcon"]');
  const controls=new Map(),hosts=new Map(),groupMemory=new Map();let uiFrame=0;
  const nodeKey=node=>String(node.className||'').split(/\s+/).find(name=>name.startsWith('st-key-'))||'';
  const disabled=node=>node.disabled||node.getAttribute('aria-disabled')==='true';
  const nativePrimary=node=>node.getAttribute('kind')==='primary'||['baseButton-primary','stBaseButton-primary'].includes(node.dataset.testid);
  const finiteRect=rect=>rect&&[rect.x??rect.left,rect.y??rect.top,rect.width,rect.height].every(Number.isFinite)&&rect.width>0&&rect.height>0;
  const visible=node=>{const rect=node.getBoundingClientRect();return finiteRect(rect)&&rect.bottom>0&&rect.top<(win.innerHeight||900);};
  const restoreProperty=(node,name,old)=>old.value?node.style.setProperty(name,old.value,old.priority):node.style.removeProperty(name);
  function releaseChevron(record){
    if(!record.chevron)return;
    const {node,old}=record.chevron;
    if(old===null)node.removeAttribute('data-qm-ui-chevron');else node.setAttribute('data-qm-ui-chevron',old);
    record.chevron=null;
  }
  function syncChevron(record){
    // Streamlit 1.64: summary > summary-content div > IconContainer span >
    // Material span. A custom icon uses stExpanderIcon, and label icons live
    // inside the separate Markdown label. Never hide either of those.
    const row=record.node.firstElementChild;
    const glyphs=row?.tagName==='DIV'?[...row.children].flatMap(child=>{
      if(child.tagName!=='SPAN')return [];
      const glyph=child.matches('[data-testid="stIconMaterial"]')?child:child.querySelector(':scope > [data-testid="stIconMaterial"]');
      return glyph&&/^(keyboard_arrow_down|keyboard_arrow_right|chevron_right)$/.test(glyph.textContent.trim())?[glyph]:[];
    }):[];
    const node=glyphs[0]||null;
    if(node===record.chevron?.node)return;
    releaseChevron(record);
    if(node){record.chevron={node,old:node.getAttribute('data-qm-ui-chevron')};node.setAttribute('data-qm-ui-chevron','true');}
  }
  function stop(record){record.tween?.kill();record.tween=null;}
  function paint(record){
    if(record.kind==='group'){
      const p=record.pose;
      // Only the one-pixel decorative rule moves; no native widget is measured per frame.
      record.line.style.transform=`translate(${p.x}px, ${p.y}px) scaleX(${p.width})`;
      record.line.style.opacity=String(p.opacity);
    }else record.node.style.setProperty(record.property,String(record.pose.amount));
  }
  function move(record,values,animate,force=false){
    if(!force&&record.target&&Object.keys(values).every(key=>Math.abs(record.target[key]-values[key])<=.001))return;
    record.target={...values};
    const changed=Object.keys(values).some(key=>Math.abs(record.pose[key]-values[key])>.001);
    if(!changed&&!record.tween)return;
    stop(record);
    if(!animate||quiet()||record.visible===false){Object.assign(record.pose,values);paint(record);return;}
    // One owned tween per record. No growing context history after repeated hover.
    record.tween=win.gsap.to(record.pose,{...values,duration:record.kind==='group'?.42:.28,
      ease:'power3.out',overwrite:true,onUpdate:()=>paint(record),onComplete:()=>{record.tween=null;paint(record);}});
  }
  function amount(record,animate=true,force=false){
    if(record.kind==='surface')return;
    const active=record.kind==='disclosure'?record.details.open:record.kind==='button'?!disabled(record.node)&&(record.hovered||record.focused):record.focused;
    move(record,{amount:active?1:0},animate&&!doc.hidden,force);
  }
  function mountHost(node,kind){
    const record={node,kind,visible:visible(node),pose:kind==='group'?{x:0,y:0,width:1,opacity:0}:{amount:0},tween:null};
    if(kind==='group'){
      record.key=nodeKey(node);record.selection=null;
      record.line=doc.createElement('span');record.line.className='qm-ui-active-line';
      record.line.setAttribute('aria-hidden','true');record.line.setAttribute('role','presentation');record.line.style.pointerEvents='none';
      record.line.style.position='absolute';record.line.style.left='0';record.line.style.top='0';record.line.style.width='1px';record.line.style.transformOrigin='0 50%';
      record.line.inert=true;node.appendChild(record.line);node.dataset.qmUiGroup='true';
    }else if(kind!=='surface'){
      record.property=kind==='disclosure'?'--qm-ui-open':'--qm-ui-focus';record.old={value:node.style.getPropertyValue(record.property),priority:node.style.getPropertyPriority(record.property)};
      record.focused=node.contains(doc.activeElement)&&doc.activeElement?.matches('input,textarea,[role="combobox"]');
      if(kind==='disclosure'){
        record.details=node.parentElement;
        record.mark=doc.createElement('span');record.mark.className='qm-ui-expander-mark';
        record.mark.setAttribute('aria-hidden','true');record.mark.setAttribute('role','presentation');record.mark.inert=true;record.mark.style.pointerEvents='none';
        for(const name of ['minus','plus']){const bar=doc.createElement('span');bar.className='qm-ui-expander-'+name;record.mark.appendChild(bar);}
        node.appendChild(record.mark);node.dataset.qmUiDisclosure='true';
        syncChevron(record);
      }else node.dataset.qmUiReady='true';
      amount(record,false);
    }
    if(kind==='composer'||kind==='group')win.__qingmengMotion?.claim(node);
    hosts.set(node,record);intersection?.observe(node);return record;
  }
  function mountButton(node){
    const owner=hosts.get(node.closest(hostSelector));
    const record={node,kind:'button',owner,visible:owner?owner.visible:visible(node),pose:{amount:0},property:'--qm-ui-hover',
      old:{value:node.style.getPropertyValue('--qm-ui-hover'),priority:node.style.getPropertyPriority('--qm-ui-hover')},
      hovered:false,focused:node===doc.activeElement,tween:null};
    node.dataset.qmUiButton='true';controls.set(node,record);amount(record,false);return record;
  }
  function forget(record){
    stop(record);
    if(record.kind==='button'){
      restoreProperty(record.node,record.property,record.old);delete record.node.dataset.qmUiButton;controls.delete(record.node);
    }else{
      intersection?.unobserve(record.node);hosts.delete(record.node);
      if(record.kind==='group'){
        groupMemory.set(record.key,{selection:record.selection,pose:{...record.pose}});
        record.line.remove();delete record.node.dataset.qmUiGroup;
      }
      else if(record.kind!=='surface'){
        restoreProperty(record.node,record.property,record.old);
        if(record.kind==='disclosure'){releaseChevron(record);record.mark.remove();delete record.node.dataset.qmUiDisclosure;}
        else delete record.node.dataset.qmUiReady;
      }
    }
  }
  function measureGroup(record){
    const buttons=[...record.node.querySelectorAll('button')].filter(node=>node.closest(groupSelector)===record.node);
    const selected=buttons.find(node=>nativePrimary(node)&&!disabled(node)),rect=record.node.getBoundingClientRect();
    if(!selected||!finiteRect(rect))return {record,selection:'',target:{...record.pose,opacity:0}};
    const buttonRect=selected.getBoundingClientRect();
    if(!finiteRect(buttonRect))return null;
    const selection=nodeKey(selected.closest('[class*="st-key-"]')||selected)||String(buttons.indexOf(selected));
    return {record,selection,target:{x:buttonRect.left-rect.left,y:buttonRect.bottom-rect.top-2,width:buttonRect.width,opacity:1}};
  }
  function refresh(){
    uiFrame=0;if(disposed||!doc.body||!win.gsap)return;
    for(const record of [...controls.values()])if(!record.node.isConnected||!record.node.matches(buttonSelector))forget(record);
    for(const record of [...hosts.values()])if(!record.node.isConnected||
      (record.kind==='disclosure'&&!ordinaryDisclosure(record.node)))forget(record);
    const scope=doc.body;
    for(const node of scope.querySelectorAll(composerSelector))if(!hosts.has(node))mountHost(node,'composer');
    for(const node of scope.querySelectorAll(groupSelector))if(!hosts.has(node))mountHost(node,'group');
    for(const node of scope.querySelectorAll(surfaceSelector))if(!hosts.has(node))mountHost(node,'surface');
    for(const node of scope.querySelectorAll(disclosureSelector))if(ordinaryDisclosure(node)){
      if(!hosts.has(node))mountHost(node,'disclosure');else{syncChevron(hosts.get(node));amount(hosts.get(node));}
    }
    for(const node of scope.querySelectorAll(buttonSelector)){
      if(!controls.has(node))mountButton(node);
      else{const record=controls.get(node);record.owner=hosts.get(node.closest(hostSelector));if(record.owner)record.visible=record.owner.visible;}
    }
    // Read all group geometry first, then write transforms. Reruns with the same
    // native selection settle directly instead of replaying an entrance.
    const measured=[...hosts.values()].filter(record=>record.kind==='group').map(measureGroup).filter(Boolean);
    for(const {record,selection,target} of measured){
      const remembered=groupMemory.get(record.key),initial=record.selection===null;
      if(initial&&remembered&&remembered.selection!==selection){Object.assign(record.pose,remembered.pose);paint(record);}
      const changed=record.selection!==selection,animate=changed&&(!initial||Boolean(remembered&&remembered.selection!==selection));
      record.selection=selection;move(record,target,animate);
      groupMemory.set(record.key,{selection,pose:{...target}});
    }
    while(groupMemory.size>64)groupMemory.delete(groupMemory.keys().next().value);
    for(const record of controls.values())if(disabled(record.node)){record.hovered=false;record.focused=false;amount(record,false);}
  }
  function schedule(){if(!disposed&&!uiFrame)uiFrame=win.requestAnimationFrame(refresh);}
  function pointer(event,enter){
    if(event.pointerType==='touch'||!(event.target instanceof win.Element))return;
    const node=event.target.closest(buttonSelector),record=controls.get(node);if(!record||(event.relatedTarget instanceof win.Node&&node.contains(event.relatedTarget)))return;
    if(enter&&disabled(node))return;record.hovered=enter;amount(record);
  }
  function focus(event,enter){
    if(!(event.target instanceof win.Element))return;
    const button=controls.get(event.target.closest(buttonSelector));
    if(button&&!(event.relatedTarget instanceof win.Node&&button.node.contains(event.relatedTarget))){button.focused=enter;amount(button);}
    const composer=hosts.get(event.target.closest(composerSelector));
    if(composer&&event.target.matches('input,textarea,[role="combobox"]')){
      composer.focused=enter||Boolean(event.relatedTarget instanceof win.Element&&composer.node.contains(event.relatedTarget)&&event.relatedTarget.matches('input,textarea,[role="combobox"]'));
      amount(composer);
    }
  }
  const intersection=typeof win.IntersectionObserver==='function'?new win.IntersectionObserver(entries=>{
    for(const entry of entries){
      const host=hosts.get(entry.target);if(!host)continue;host.visible=entry.isIntersecting;
      if(host.visible)schedule();
      if(!host.visible){if(host.kind==='group'){const measured=measureGroup(host);if(measured)move(host,measured.target,false,true);}else amount(host,false,true);}
      for(const record of controls.values())if(record.owner===host){record.visible=host.visible;if(!host.visible){record.hovered=false;amount(record,false,true);}}
    }
  },{threshold:0}):null;
  const mutations=new win.MutationObserver(records=>{
    if(records.some(record=>{
      if(record.type==='attributes')return controls.has(record.target)||record.target.matches(buttonSelector)||
        record.target.closest(disclosureSelector)||(record.attributeName==='open'&&record.target.matches('[data-testid="stExpander"] > details'));
      const nodes=[...record.addedNodes,...record.removedNodes];
      if(nodes.every(node=>node instanceof win.Element&&node.matches('.qm-ui-active-line,.qm-ui-expander-mark')))return false;
      if(record.target instanceof win.Element&&record.target.closest(roots))return true;
      return nodes.some(node=>node instanceof win.Element&&(node.matches(roots)||node.querySelector(roots)));
    }))schedule();
  });
  mutations.observe(doc,{childList:true,subtree:true,attributes:true,attributeFilter:['data-testid','kind','disabled','aria-disabled','open']});
  function mode(){
    if(quiet())settle();
    for(const record of controls.values()){if(doc.hidden)record.hovered=false;amount(record,false,true);}
    for(const record of hosts.values())if(record.kind==='composer'||record.kind==='disclosure')amount(record,false,true);
    for(const record of hosts.values())if(record.kind==='group'){const measured=measureGroup(record);if(measured)move(record,measured.target,false,true);}
    schedule();
  }
  function resize(){
    for(const record of hosts.values())if(record.kind==='group'){stop(record);record.target=null;}
    schedule();
  }
  function dispose(){
    if(disposed)return;disposed=true;settle();if(uiFrame)win.cancelAnimationFrame(uiFrame);uiFrame=0;
    mutations.disconnect();intersection?.disconnect();for(const record of [...controls.values(),...hosts.values()])forget(record);groupMemory.clear();
    abort.abort();media.removeEventListener('change',mode);
  }
  doc.addEventListener('visibilitychange',mode,{signal:abort.signal});
  win.addEventListener('qm-motion-preference-change',mode,{signal:abort.signal});
  win.addEventListener('pagehide',dispose,{signal:abort.signal});media.addEventListener('change',mode);
  doc.addEventListener('pointerover',event=>pointer(event,true),{signal:abort.signal,passive:true});
  doc.addEventListener('pointerout',event=>pointer(event,false),{signal:abort.signal,passive:true});
  doc.addEventListener('focusin',event=>focus(event,true),{signal:abort.signal});
  doc.addEventListener('focusout',event=>focus(event,false),{signal:abort.signal});
  win.addEventListener('resize',resize,{signal:abort.signal,passive:true});
  win.QMFeatureWorkflow={version:VERSION,reveal,refresh:schedule,dispose,getState:()=>({hosts:hosts.size,buttons:controls.size,
    rules:[...hosts.values()].filter(record=>record.kind==='group').length,disclosures:[...hosts.values()].filter(record=>record.kind==='disclosure').length,
    running:[...hosts.values(),...controls.values()].filter(record=>record.tween?.isActive()).length})};
  schedule();
})(window);
