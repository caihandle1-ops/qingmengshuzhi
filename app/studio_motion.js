/* Local visual state only: native widgets remain the only business controls. */
(() => {
  const VERSION='2026-10-05.10';
  if(window.__qmStudioMotion?.version===VERSION){window.__qmStudioMotion.refresh();return;}
  window.__qmStudioMotion?.dispose();
  const abort=new AbortController(),reduced=matchMedia('(prefers-reduced-motion: reduce)'),fine=matchMedia('(pointer:fine)');
  const effects=new Set(),decorations=new Set(),devices=new Set(),drawers=new WeakSet(),visibleDevices=new WeakMap();
  const nodeEffects=new WeakMap(),pendingDrawerExits=new Map();
  const drawerKeys=new Set();
  const resultKeys=new Set(),resultStages=new Set(),resultVisible=new WeakMap(),tiltedScenes=new Set();
  let scenePointerFrame=0,scenePointer=null;
  let frame=0,pillFrame=0,route='',observedRoute='',arrival=null,arrivalTarget=null,pending=null,pill=null,focusReturn=null,focusFrame=0,focusSettleFrame=0;
  let navObserver=null,navGroup=null,navLabel=null;
  let markerRequired=false;
  const root=document.documentElement;
  root.dataset.qmStudioMotion=VERSION;
  const active=()=>!reduced.matches&&!document.hidden;
  function animate(el,frames,options){if(!active()||!el.animate)return;nodeEffects.get(el)?.cancel();const animation=el.animate(frames,options);nodeEffects.set(el,animation);effects.add(animation);animation.finished.catch(()=>{}).finally(()=>{effects.delete(animation);if(nodeEffects.get(el)===animation)nodeEffects.delete(el);});return animation;}
  function decorate(rect,classname){const el=document.createElement('div');el.className=classname;el.setAttribute('aria-hidden','true');Object.assign(el.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});document.body.appendChild(el);decorations.add(el);return el;}
  function cancelFocusFrames(){if(focusFrame)cancelAnimationFrame(focusFrame);if(focusSettleFrame)cancelAnimationFrame(focusSettleFrame);focusFrame=0;focusSettleFrame=0;}
  function cancelFocusReturn(){cancelFocusFrames();focusReturn=null;}
  function discardPendingExits(){for(const record of pendingDrawerExits.values()){record.visual.dispose();record.entrance?.play?.();}pendingDrawerExits.clear();}
  function resetScene(scene){for(const key of ['--scene-tilt-x','--scene-tilt-y'])scene.style.setProperty(key,'0deg');for(const key of ['--scene-drift-x','--scene-drift-y'])scene.style.setProperty(key,'0px');tiltedScenes.delete(scene);}
  function cleanup(){discardPendingExits();pending=null;arrival=null;for(const a of effects)a.cancel();effects.clear();for(const el of decorations)el.remove();decorations.clear();if(frame)cancelAnimationFrame(frame);if(pillFrame)cancelAnimationFrame(pillFrame);if(scenePointerFrame)cancelAnimationFrame(scenePointerFrame);scenePointerFrame=0;scenePointer=null;for(const scene of tiltedScenes)resetScene(scene);frame=0;pillFrame=0;cancelFocusFrames();}
  function finishDrawerExits(){for(const [panel,record] of pendingDrawerExits){if(!panel.isConnected){if(document.querySelector('.'+CSS.escape(record.key)))record.visual.dispose();else {drawerKeys.delete(record.key);record.visual.play();}pendingDrawerExits.delete(panel);}else if(performance.now()-record.started>1400){record.visual.dispose();record.entrance?.play?.();pendingDrawerExits.delete(panel);}}}
  function focusRequestExpired(request){return performance.now()-request.started>1500||request.attempts>=4;}
  function returnButton(request){return document.querySelector('.'+CSS.escape(request.key)+' button');}
  function restoreDrawerFocus(){
    const request=focusReturn;
    if(!request)return;
    if(focusRequestExpired(request)){cancelFocusReturn();return;}
    if(document.hidden||focusFrame||focusSettleFrame||document.querySelector('[class*="st-key-answer_sources_panel_"]'))return;
    const initial=returnButton(request);
    if(!initial||(initial===request.button&&document.activeElement===initial))return;
    // Wait through two paints, then find the native control again. React may
    // replace a node which was briefly present immediately after drawer close.
    focusFrame=requestAnimationFrame(()=>{
      focusFrame=0;
      if(focusReturn!==request||document.hidden)return;
      const candidate=returnButton(request);
      focusSettleFrame=requestAnimationFrame(()=>{
        focusSettleFrame=0;
        if(focusReturn!==request||document.hidden)return;
        if(focusRequestExpired(request)){cancelFocusReturn();return;}
        if(document.querySelector('[class*="st-key-answer_sources_panel_"]'))return;
        const button=returnButton(request);
        if(!button)return;
        if(button!==candidate){refresh();return;}
        if(!request.scrollRestored){const main=document.querySelector('[data-testid="stMain"]');if(main&&request.scroll!==null)main.scrollTop=request.scroll;request.scrollRestored=true;}
        button.focus({preventScroll:true});request.button=button;request.attempts++;
        // Retain a bounded recovery record for a subsequent native remount.
        // A user click, Tab, new route or disposal cancels it immediately.
      });
    });
  }
  function observeNavigation(group,label){if(navGroup!==group){if(navGroup){navGroup.dataset.studioNavReady='false';navObserver?.unobserve(navGroup);}navGroup=group;if(group)navObserver?.observe(group);}if(navLabel!==label){if(navLabel)navObserver?.unobserve(navLabel);navLabel=label;if(label)navObserver?.observe(label);}}
  function staleNavigation(){if(navGroup)navGroup.dataset.studioNavReady='false';if(pill)pill.hidden=true;refresh();settlePill();}
  function movePill(){const group=document.querySelector('.st-key-navigation [role="radiogroup"]'),input=group?.querySelector('input:checked');
    const flagged=input?null:group?.querySelector('[data-selected="true"],[aria-checked="true"]');
    const selected=input?.closest('label[data-baseweb="radio"]')||input?.closest('label')||input?.closest('[data-testid="stRadioOption"]')||flagged?.closest('label[data-baseweb="radio"]')||flagged?.querySelector?.('label[data-baseweb="radio"]')||flagged;
    observeNavigation(group||null,selected||null);
    if(!group||!selected||!group.contains(selected)){if(group)group.dataset.studioNavReady='false';if(pill)pill.hidden=true;return;}
    const base=group.getBoundingClientRect(),box=selected.getBoundingClientRect();
    if(![base.width,base.height,box.width,box.height].every(value=>Number.isFinite(value)&&value>0)){group.dataset.studioNavReady='false';if(pill)pill.hidden=true;return;}
    if(!pill?.isConnected||!group.contains(pill)){pill?.remove();pill=document.createElement('span');pill.className='studio-nav-indicator';pill.setAttribute('aria-hidden','true');group.prepend(pill);}
    pill.style.width=box.width+'px';pill.style.height=box.height+'px';pill.style.transform='translate('+ (box.left-base.left)+'px,'+(box.top-base.top)+'px)';pill.hidden=false;group.dataset.studioNavReady='true';}
  function settlePill(){if(pillFrame)return;let paints=2;const settle=()=>{pillFrame=0;movePill();if(--paints)pillFrame=requestAnimationFrame(settle);};pillFrame=requestAnimationFrame(settle);}
  const routeSelector='.st-key-workspace_hero,[class*="st-key-guided_intro_"],.st-key-qa_composer,.st-key-workspace_search_results';
  function routeTarget(location,sceneContract){
    // An explicit view marker, when supplied by the app, also covers React
    // reusing the same native container for a different subview.
    const marker=document.querySelector('[data-studio-view]');
    if(marker){markerRequired=true;if(marker.getAttribute(sceneContract?'data-studio-view-scene':'data-studio-view')!==location)return null;}
    else if(markerRequired)return null;
    const candidate=document.querySelector(routeSelector);
    return candidate&&(marker||!arrival||arrival.initial||candidate!==arrival.oldTarget)?candidate:null;
  }
  function revealFeatureScene(feature,transition=false){
    if(!active())return;
    // Individual properties compose with the CSS final arrangement. Never animate
    // transform itself, the heading, or a parent that owns native controls.
    const scene=feature.getAttribute?.('data-feature-scene'),counts={};
    const curtain=transition&&feature.querySelector?.('[data-feature-curtain]');
    if(curtain)animate(curtain,[{opacity:.96,transform:'scaleX(1)',offset:0},{opacity:.9,transform:'scaleX(.88)',offset:.2},{opacity:0,transform:'scaleX(0)',offset:1}],{duration:640,easing:'cubic-bezier(.65,0,.35,1)'});
    const pieces=Array.from(feature.querySelectorAll?.('[data-feature-piece]')||[]).slice(0,12);
    pieces.forEach((piece,index)=>{
      const kind=piece.getAttribute?.('data-feature-piece')||'',ordinal=counts[kind]||0;counts[kind]=ordinal+1;
      let from={opacity:.12,translate:(index%2?-36:36)+'px 24px',rotate:'0deg',scale:'1'},duration=680,delay=Math.min(index*38,190),frames;
      if(scene==='qa'){
        if(kind==='question'){from={opacity:0,translate:'-74px -24px',rotate:'-12deg',scale:'.82'};duration=720;delay=0;}
        else if(kind==='answer'){from={opacity:0,translate:'66px 38px',rotate:'10deg',scale:'.78'};duration=650;delay=190;}
        else if(kind==='signal'&&ordinal===0){from={opacity:0,translate:'0px 0px',rotate:'-30deg',scale:'.58'};duration=800;delay=0;}
        else {from={opacity:0,translate:'-60px 0px',rotate:'0deg',scale:'.18 1'};duration=670;delay=100;}
      }else if(scene==='scope'){
        if(kind==='core'){from={opacity:0,translate:'28px 32px',rotate:'4deg',scale:'.84'};duration=760;delay=0;}
        else {from={opacity:0,translate:(-94-ordinal*10)+'px '+((ordinal-2.5)*7)+'px',rotate:((ordinal-2.5)*3)+'deg',scale:'.92 1'};duration=620;delay=ordinal*44;}
      }else if(scene==='counter'){
        if(kind==='claim'){from={opacity:0,translate:'-72px -18px',rotate:'-14deg',scale:'.84'};duration=730;delay=0;}
        else if(kind==='evidence'){from={opacity:0,translate:'78px 28px',rotate:'14deg',scale:'.84'};duration=730;delay=60;}
        else if(kind==='lens'){
          from={opacity:0,translate:'-104px 18px',rotate:'-26deg',scale:'.72'};duration=860;delay=40;
          frames=[{...from,offset:0},{opacity:1,translate:'-52px 4px',rotate:'-12deg',scale:'1',offset:.42}];
        }
      }else if(scene==='replay'){
        if(kind==='track'){from={opacity:0,translate:'-96px 20px',rotate:'8deg',scale:'.4 1'};duration=750;delay=0;}
        else if(kind==='record'){from={opacity:0,translate:'-84px '+(42-ordinal*12)+'px',rotate:(14-ordinal*6)+'deg',scale:'.86'};duration=620;delay=90+ordinal*90;}
        else {from={opacity:0,translate:'0px 20px',rotate:'0deg',scale:'1'};duration=460;delay=380;}
      }else if(scene==='assets'){
        if(kind==='index'){from={opacity:0,translate:'0px 58px',rotate:'0deg',scale:'.92 1'};duration=700;delay=0;}
        else {from={opacity:0,translate:([72,24,-26,-78][ordinal%4])+'px 68px',rotate:([18,8,-8,-20][ordinal%4])+'deg',scale:'.84'};duration=690;delay=40+ordinal*45;}
      }
      const end={opacity:1,translate:'0px 0px',rotate:'0deg',scale:'1'};
      animate(piece,frames?[...frames,{...end,offset:1}]:[from,end],
        {duration,delay,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    });
  }
  function incoming(){const header=document.querySelector('[data-studio-location]'),scene=header?.getAttribute('data-studio-scene'),location=scene||header?.getAttribute('data-studio-location');if(!location)return;
    if(header.getAttribute('data-studio-view-required')==='true')markerRequired=true;
    if(location!==observedRoute){const previous=observedRoute;observedRoute=location;root.dataset.qmStudioRouteObserved=location;root.dataset.qmStudioScene=location;
      arrival={location,previous,initial:!previous,oldTarget:pending?.oldTarget||arrivalTarget,intent:pending,started:pending?.started??performance.now()};
      if(previous){drawerKeys.clear();cancelFocusReturn();discardPendingExits();window.__qingmengMotion?.discardExits?.();const main=document.querySelector('[data-testid="stMain"]');if(main)main.scrollTop=0;settlePill();}
    }
    if(!arrival||arrival.location!==location)return;
    const target=routeTarget(location,Boolean(scene));
    const completed=!target&&document.querySelector('[data-studio-view]')?.getAttribute(scene?'data-studio-view-scene':'data-studio-view')===location;
    if((!target&&!completed)||target?.isConnected===false){root.dataset.qmStudioLast='route-awaiting-content';return;}
    const box=target?.getBoundingClientRect();if(target&&!(box.width>0&&box.height>0))return;
    const request=arrival;arrival=null;pending=null;route=location;arrivalTarget=target;
    root.dataset.qmStudioRoute=location;root.dataset.qmRouteWaitMs=Math.max(0,performance.now()-request.started).toFixed(2);
    if(!target||!active()){root.dataset.qmStudioLast='route-static';return;}
    const feature=target.querySelector?.('[data-feature-scene]');
    const stationaryHeading=feature||target.querySelector?.('.deep-page');
    if(request.initial){if(feature)revealFeatureScene(feature);root.dataset.qmStudioLast='route-static';return;}
    if(window.__qmRouteStage?.arrive?.(target,{location,previous:request.previous})){if(feature)revealFeatureScene(feature);root.dataset.qmStudioLast='route-connected';return;}
    window.__qingmengMotion?.claim?.(target);
    // A single content owner replaces the large, painted card-to-page morph.
    animate(target,stationaryHeading?[{opacity:.35},{opacity:1}]:[{opacity:.35,transform:'translateY('+(request.intent?.back?-16:18)+'px)'},{opacity:1,transform:'translateY(0)'}],{duration:480,easing:'cubic-bezier(.16,1,.3,1)'});
    if(feature)revealFeatureScene(feature,true);
    root.dataset.qmStudioLast='route';}
  // Result identities survive native remounts and local disclosures. Only
  // explicitly marked decorative pieces move; values and form controls do not.
  function revealResult(stage){
    if(!stage.isConnected||document.hidden)return;
    const scene=stage.getAttribute('data-result-scene'),id=stage.getAttribute('data-result-id');
    if(!scene||!id)return;
    const key=scene+':'+id;
    window.__qingmengMotion?.claim?.(stage);
    if(resultKeys.has(key))return;
    resultKeys.add(key);while(resultKeys.size>256)resultKeys.delete(resultKeys.values().next().value);
    if(!active())return;
    const pieces=Array.from(stage.querySelectorAll?.('[data-result-piece]')||[]).slice(0,12);
    pieces.forEach((piece,index)=>{
      const kind=piece.getAttribute?.('data-result-piece')||'';
      let from={opacity:0,translate:'0px 20px',scale:'.85',rotate:'0deg'};
      let duration=700,delay=Math.min(index*36,180),frames;
      if(scene==='scope')from={opacity:.2,translate:'-44px 0px',scale:'.08 1',rotate:'0deg'};
      else if(scene==='counter')from={opacity:0,translate:'22px -16px',scale:'.78',rotate:'-9deg'};
      else if(scene==='replay')from={opacity:0,translate:(index%2?38:-38)+'px 14px',scale:'.9',rotate:(index%2?7:-7)+'deg'};
      else if(scene==='assets')from={opacity:0,translate:'24px 14px',scale:'.76',rotate:'12deg'};
      else if(scene==='compare'){
        from=kind==='connector'?{opacity:0,translate:'-120px 0px',scale:'.02 1',rotate:'0deg'}:
          kind==='focus'?{opacity:0,translate:'48px -32px',scale:'.28',rotate:'-42deg'}:
          {opacity:0,translate:(index%2?140:-140)+'px 30px',scale:'.5 1',rotate:(index%2?16:-16)+'deg'};
        duration=760;delay=Math.min(index*48,120);
      }else if(scene==='reading'){
        from=kind==='connector'?{opacity:0,translate:'-86px 0px',scale:'.01 1',rotate:'0deg'}:
          {opacity:0,translate:'72px 26px',scale:'.72 1',rotate:'18deg'};
        duration=720;delay=Math.min(index*70,140);
      }else if(scene==='enterprise'){
        from={opacity:0,translate:(index%2?150:-150)+'px '+(42-index*8)+'px',scale:'.22 1',rotate:(index%2?-18:18)+'deg'};
        duration=760;delay=Math.min(index*40,120);
      }else if(scene==='evaluation'){
        from={opacity:0,translate:'0px -56px',scale:'1.65',rotate:'-26deg'};
        frames=[{...from,offset:0},{opacity:.9,translate:'0px -12px',scale:'1.12',rotate:'-5deg',offset:.52}];
        duration=660;delay=Math.min(index*56,180);
      }else if(scene==='reviews'){
        from={opacity:0,translate:(index%2?86:-86)+'px 84px',scale:'.8',rotate:(index%2?24:-24)+'deg'};
        duration=720;delay=Math.min(index*48,144);
      }else if(scene==='report'){
        from={opacity:0,translate:'96px -42px',scale:'1.35',rotate:'28deg'};
        duration=780;delay=Math.min(index*48,96);
      }
      const end={opacity:1,translate:'0px 0px',scale:'1',rotate:'0deg'};
      animate(piece,frames?[...frames,{...end,offset:1}]:[from,end],{duration,delay,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    });
    for(const sweep of Array.from(stage.querySelectorAll?.('[data-result-sweep]')||[]).slice(0,2)){
      const distance=Math.max(0,(sweep.parentElement?.getBoundingClientRect().width||stage.getBoundingClientRect().width)-sweep.getBoundingClientRect().width);
      const frames=scene==='counter'?[{opacity:0,transform:'translateX(0)',offset:0},{opacity:.9,transform:'translateX('+(distance*.32)+'px)',offset:.32},{opacity:0,transform:'translateX('+distance+'px)',offset:1}]:[{opacity:0,transform:'scaleX(0)',offset:0},{opacity:.9,transform:'scaleX(.38)',offset:.32},{opacity:0,transform:'scaleX(1)',offset:1}];
      animate(sweep,frames,{duration:880,easing:'cubic-bezier(.65,0,.35,1)'});
    }
    root.dataset.qmStudioResult=scene;
  }
  const observerDevices=new IntersectionObserver(entries=>{for(const entry of entries){visibleDevices.set(entry.target,entry.isIntersecting);entry.target.classList.toggle('is-paused',!entry.isIntersecting||document.hidden||reduced.matches);}}, {threshold:.06});
  const observerResults=new IntersectionObserver(entries=>{for(const entry of entries){resultVisible.set(entry.target,entry.isIntersecting);if(entry.isIntersecting)revealResult(entry.target);}}, {threshold:.08});
  function scan(){frame=0;if(!document.body)return;movePill();incoming();finishDrawerExits();
    restoreDrawerFocus();
    for(const stage of document.querySelectorAll('[data-result-scene][data-result-id]')){
      if(stage.closest?.('[data-qm-visual-exit]'))continue;
      if(!resultStages.has(stage)){resultStages.add(stage);observerResults.observe(stage);window.__qingmengMotion?.claim?.(stage);}
      if(resultVisible.get(stage))revealResult(stage);
    }
    for(const stage of resultStages)if(!stage.isConnected){observerResults.unobserve(stage);resultStages.delete(stage);}
    for(const scene of tiltedScenes)if(!scene.isConnected)tiltedScenes.delete(scene);
    for(const device of document.querySelectorAll('.studio-financial-device'))if(!device.closest?.('[data-qm-visual-exit]')&&!devices.has(device)){devices.add(device);observerDevices.observe(device);device.classList.toggle('is-paused',!active());}
    for(const device of devices)if(!device.isConnected){observerDevices.unobserve(device);devices.delete(device);}
    for(const panel of document.querySelectorAll('[class*="st-key-answer_sources_panel_"]'))if(!drawers.has(panel)){
      drawers.add(panel);panel.setAttribute('role','complementary');panel.setAttribute('aria-label','回答来源依据');
      window.__qingmengMotion?.claim?.(panel);
      const key=Array.from(panel.classList).find(name=>name.startsWith('st-key-answer_sources_panel_'));
      if(drawerKeys.has(key))continue;
      drawerKeys.add(key);
      if(window.__qmEvidenceStage?.owns?.(panel))window.__qmEvidenceStage.open(panel);
      else animate(panel,[{transform:'translateX(110%)',opacity:.2},{transform:'translateX(0)',opacity:1}],{duration:580,easing:'cubic-bezier(.16,1,.3,1)'});
      const button=panel.querySelector('[class*="st-key-answer_sources_close_"] button');button?.focus({preventScroll:true});root.dataset.qmStudioLast='evidence-open';}
  }
  const refresh=()=>{if(!frame)frame=requestAnimationFrame(scan);};
  if(typeof ResizeObserver==='function')navObserver=new ResizeObserver(staleNavigation);
  const mutation=new MutationObserver(records=>{const navChanged=records.some(record=>record.type==='attributes'&&record.target.closest?.('.st-key-navigation'));
    const routeChanged=records.some(record=>record.type==='attributes'&&['data-studio-view','data-studio-location','data-studio-scene','data-studio-view-scene','data-studio-view-required','data-result-id'].includes(record.attributeName));
    if(navChanged)settlePill();if(navChanged||routeChanged||records.some(record=>record.type==='childList'&&Array.from(record.addedNodes||[]).concat(Array.from(record.removedNodes||[])).some(node=>node.nodeType===1&&!node.matches?.('.studio-nav-indicator,.studio-route-morph,.studio-drawer-exit,.qm-motion-exit'))))refresh();});
  mutation.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['checked','aria-checked','data-selected','data-studio-view','data-studio-location','data-studio-scene','data-studio-view-scene','data-studio-view-required','data-result-id']});
  const nativeNavigationChanged=event=>{if(event.target.closest?.('.st-key-navigation')){refresh();settlePill();}};
  document.addEventListener('input',nativeNavigationChanged,{capture:true,passive:true,signal:abort.signal});
  document.addEventListener('change',nativeNavigationChanged,{capture:true,passive:true,signal:abort.signal});
  document.addEventListener('click',event=>{const started=performance.now(),button=event.target.closest?.('button,label');const owner=button?.closest('[class*="st-key-"]');const name=owner?.className||'';
    if(!/answer_sources_close_/.test(name))cancelFocusReturn();
    if(!button)return;
    if(button.closest('.st-key-navigation')||/workspace_open_|workspace_feature_|navigation_home|_back|navigation_previous|guided_card_/.test(name)){root.dataset.qmStudioIntent='navigation';pending={back:/_back|navigation_home|navigation_previous/.test(name),started,oldTarget:document.querySelector(routeSelector)};animate(button,[{opacity:.72},{opacity:1}],{duration:160,easing:'ease-out'});}
    const navigationLabel=button.closest('.st-key-navigation');
    const realSceneEntry=navigationLabel||/workspace_open_|guided_card_workspace_feature_|guided_card_workspace_(enterprise|library|evaluation)|navigation_home|navigation_previous|workspace_layer_back|asset_back_home|navigation_back_previous|enterprise_back_home|guided_card_asset_(import|library|evaluation|review)_entry|workspace_empty_assets/.test(name);
    const selectedLabel=navigationLabel&&button.querySelector?.('input:checked');
    if(realSceneEntry&&!selectedLabel)window.__qmRouteStage?.begin?.(button,{back:/navigation_home|navigation_previous|_back/.test(name),scene:observedRoute});
    if(/answer_sources_(close|toggle)_|comparison_source_/.test(name)){
      const toggleClass=String(name).split(/\s+/).find(c=>c.startsWith('st-key-answer_sources_toggle_')||c.startsWith('st-key-comparison_source_'));
      const panelClass=toggleClass?.replace(/answer_sources_toggle_|comparison_source_/,'answer_sources_panel_');
      const panel=button.closest('[class*="st-key-answer_sources_panel_"]')||(panelClass?document.querySelector('.'+CSS.escape(panelClass)):null);
      if(panel){
        const panelKey=Array.from(panel.classList).find(c=>c.startsWith('st-key-answer_sources_panel_'));
        const evidence=window.__qmEvidenceStage,owned=evidence?.owns?.(panel);
        const key=(owned?evidence.returnKey(panel):null)||panelKey?.replace('answer_sources_panel_','answer_sources_toggle_');
        cancelFocusReturn();if(key)focusReturn={key,scroll:document.querySelector('[data-testid="stMain"]')?.scrollTop??null,started:performance.now(),attempts:0,button:null,scrollRestored:false};
        if(owned){drawerKeys.delete(panelKey);evidence.close(panel);}
        else {pendingDrawerExits.get(panel)?.visual.dispose();const entrance=nodeEffects.get(panel);entrance?.pause?.();const visual=window.__qingmengMotion?.captureExit?.(panel,{direction:'right'});if(visual&&panelKey)pendingDrawerExits.set(panel,{visual,key:panelKey,entrance,started:performance.now()});else entrance?.play?.();}
      }
      else if(panelClass)drawerKeys.delete(panelClass);
      refresh();root.dataset.qmStudioLast='evidence-close';}
    root.dataset.qmStudioClickWorkMs=Math.max(0,performance.now()-started).toFixed(2);
  },{capture:true,passive:true,signal:abort.signal});
  document.addEventListener('keydown',event=>{if(event.key!=='Escape'){if(event.key==='Tab')cancelFocusReturn();return;}const panel=document.querySelector('[class*="st-key-answer_sources_panel_"]');if(panel)panel.querySelector('[class*="st-key-answer_sources_close_"] button')?.click();},{signal:abort.signal});
  function updateDevicePointer(event){const device=event.target.closest?.('.studio-financial-device');if(!device)return;const rect=device.getBoundingClientRect(),x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));device.style.setProperty('--device-rotate-x',(2.5-y*5)+'deg');device.style.setProperty('--device-rotate-y',(x*8-4)+'deg');device.style.setProperty('--device-light-x',x*100+'%');device.style.setProperty('--device-light-y',y*100+'%');}
  function resetDevicePointer(event){const device=event.target.closest?.('.studio-financial-device');if(device&&!device.contains(event.relatedTarget)){device.style.setProperty('--device-rotate-x','0deg');device.style.setProperty('--device-rotate-y','0deg');}}
  document.addEventListener('pointermove',event=>{
    if(!active()||!fine.matches)return;
    updateDevicePointer(event);
    const scene=event.target.closest?.('[data-feature-scene]');if(!scene)return;
    scenePointer={scene,x:event.clientX,y:event.clientY};if(scenePointerFrame)return;
    scenePointerFrame=requestAnimationFrame(()=>{
      scenePointerFrame=0;const point=scenePointer;scenePointer=null;
      if(!point||!point.scene.isConnected||!active()||!fine.matches)return;
      const rect=point.scene.getBoundingClientRect();if(!rect.width||!rect.height)return;
      const x=Math.max(-.5,Math.min(.5,(point.x-rect.left)/rect.width-.5)),y=Math.max(-.5,Math.min(.5,(point.y-rect.top)/rect.height-.5));
      point.scene.style.setProperty('--scene-tilt-x',(-y*9)+'deg');point.scene.style.setProperty('--scene-tilt-y',(x*12)+'deg');
      point.scene.style.setProperty('--scene-drift-x',(x*14)+'px');point.scene.style.setProperty('--scene-drift-y',(y*10)+'px');tiltedScenes.add(point.scene);
    });
  },{passive:true,signal:abort.signal});
  document.addEventListener('pointerout',event=>{resetDevicePointer(event);const scene=event.target.closest?.('[data-feature-scene]');if(scene&&!scene.contains(event.relatedTarget)){if(scenePointer?.scene===scene)scenePointer=null;resetScene(scene);}},{passive:true,signal:abort.signal});
  const mediaChange=()=>{if(!active())cleanup();for(const device of devices)device.classList.toggle('is-paused',!active()||visibleDevices.get(device)===false);refresh();};
  reduced.addEventListener('change',mediaChange);document.addEventListener('visibilitychange',mediaChange,{signal:abort.signal});window.addEventListener('resize',()=>{discardPendingExits();window.__qingmengMotion?.discardExits?.();staleNavigation();},{passive:true,signal:abort.signal});
  window.__qmStudioMotion={version:VERSION,refresh,dispose(){cancelFocusReturn();cleanup();mutation.disconnect();observerDevices.disconnect();observerResults.disconnect();navObserver?.disconnect();if(navGroup)navGroup.dataset.studioNavReady='false';abort.abort();reduced.removeEventListener('change',mediaChange);pill?.remove();devices.clear();resultStages.clear();resultKeys.clear();}};refresh();
})();
