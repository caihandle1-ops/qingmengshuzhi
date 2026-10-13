'use strict';
(async()=>{
 const specs=await fetch('scenes.json').then(response=>{if(!response.ok)throw Error('Scene snapshot unavailable');return response.json();});
 const stage=document.getElementById('stage'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const labels={home:'研究工作台',qa:'财报问数',scope:'口径核验',counter:'反证核验',replay:'证据复演',assets:'数据资产'};
 const spreadWords={qa:'TRACE',scope:'ALIGN',counter:'RECHECK',replay:'REPLAY',assets:'INDEX'};
 let current='',mode='presentation',hero=null,theaterOpen=false;
 const quiet=()=>reduced.matches||mode==='research'||theaterOpen||Boolean(document.querySelector('[data-feature-inline-mounted="true"]'));
 const controller=QMFeatureSceneMotion.create({document,quiet});
 const renderHero=()=>hero?.contentWindow?.postMessage({type:'streamlit:render',args:{motion:{version:1,mode}}},location.origin);
 function mount(scene,remount=false){
   const changed=current!==scene;
   if(!changed&&!remount){controller.refresh();renderHero();return;}
   if(changed){current=scene;controller.setRoute(scene);window.QMFeatureTheater?.setRoute(scene);}
   if(scene==='home'){
     if(hero){renderHero();return;}
     stage.replaceChildren();hero=document.createElement('iframe');hero.src='hero/index.html';hero.title='三幕财报研究装置';hero.className='hero-host';stage.appendChild(hero);controller.sync([]);window.QMFeatureTheater?.syncInline([]);
   }else{
     hero=null;const spec=specs[scene],wrapper=document.createElement('section');wrapper.className='st-key-feature_intro_'+scene;
     // Mirror the production spread coordinate system so title masks, camera
     // motion and cross-column overlap are exercised on the same ancestors.
     const spread=document.createElement('section');spread.className='feature-spread';spread.dataset.featureSpread=scene;
     const word=document.createElement('div');word.className='feature-spread-word';word.setAttribute('data-feature-type','');word.setAttribute('aria-hidden','true');word.textContent=spreadWords[scene];
     const heading=document.createElement('header');heading.className='feature-spread-heading';
     const eyebrow=document.createElement('div');eyebrow.className='feature-eyebrow';eyebrow.textContent=spec.eyebrow;
     const titleMask=document.createElement('div');titleMask.className='feature-title-mask';titleMask.setAttribute('data-feature-title-mask','');
     const title=document.createElement('h2');title.textContent=labels[scene];
     titleMask.appendChild(title);heading.append(eyebrow,titleMask);
     const visual=document.createElement('div');visual.className=`feature-scene feature-scene-${scene} feature-scene--${scene}`;visual.dataset.featureScene=scene;visual.dataset.featureInline=scene;visual.setAttribute('role','group');visual.setAttribute('aria-label',spec.label);
     const art=document.createElement('div');art.className='feature-scene-art';art.setAttribute('aria-hidden','true');art.innerHTML=spec.art;
     const curtain=document.createElement('span');curtain.className='feature-scene-curtain';curtain.setAttribute('data-feature-curtain','');curtain.setAttribute('aria-hidden','true');
     const copy=document.createElement('footer');copy.className='feature-spread-copy';
     const statement=document.createElement('p');statement.className='feature-statement';statement.textContent=spec.statement;
     const detail=document.createElement('div'),note=document.createElement('p');note.className='feature-intro-copy';note.textContent=spec.caption;detail.appendChild(note);copy.append(statement,detail);
     visual.append(art,curtain);spread.append(word,heading,visual,copy);wrapper.appendChild(spread);stage.replaceChildren(wrapper);
     window.QMFeatureTheater?.syncInline([visual]);if(changed)controller.enter(visual);controller.sync([visual]);
   }
   document.querySelectorAll('[data-nav]').forEach(node=>node.classList.toggle('selected',node.dataset.nav===scene));
 }
 function sync(){controller.refresh();renderHero();}
 window.addEventListener('qm-feature-theater-change',event=>{theaterOpen=event.detail?.open===true;controller.refresh();});
 window.addEventListener('qm-feature-inline-change',()=>controller.refresh());
 document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);
 window.addEventListener('message',event=>{
   if(event.origin!==location.origin)return;
   if(hero&&event.source===hero.contentWindow&&event.data?.type==='streamlit:componentReady'){renderHero();return;}
   if(event.source!==window.parent)return;const data=event.data||{};
   if(data.type==='gallery:view'&&Object.hasOwn(labels,data.scene)&&['presentation','research'].includes(data.mode)){mode=data.mode;document.documentElement.dataset.qmMotionMode=mode;window.dispatchEvent(new CustomEvent('qm-motion-preference-change'));mount(data.scene);sync();}
   else if(data.type==='gallery:remount')mount(current,true);
   else if(data.type==='gallery:inspect')window.parent.postMessage({type:'gallery:state',state:{scene:current,mode,osReduced:reduced.matches,feature:controller.getState(),inline:window.QMFeatureTheater?.getInlineState(),hero:hero?.contentWindow?.__qmImmersiveHero?.getState()||null,visualAcceptance:'pending'}},location.origin);
 });
 window.addEventListener('pagehide',()=>{controller.dispose();window.QMFeatureTheater?.dispose();},{once:true});
 window.parent.postMessage({type:'gallery:ready'},location.origin);
})().catch(error=>{document.getElementById('stage').textContent='验收资源未加载：'+String(error.message);});
