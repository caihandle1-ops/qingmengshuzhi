(() => {
  'use strict';
  const $ = id => document.getElementById(id), shell = $('director');
  const abort = new AbortController(), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let navAbort = new AbortController(), editorAbort = new AbortController(), focusAbort = new AbortController(), stageAbort = new AbortController();
  let disposed = false, onscreen = true, animations = [], editing = false, lastHeight = 0, exiting = false, enhanced = true;
  const listen = (node, type, fn, signal = abort.signal) => node.addEventListener(type, fn, {signal});
  const send = (type, values = {}) => parent.postMessage({isStreamlitMessage:true, type, ...values}, '*');
  const node = (tag, className, text) => {
    const result = document.createElement(tag); if (className) result.className = className;
    if (text !== undefined && text !== null) result.textContent = String(text); return result;
  };
  const button = (label, className, action, signal = abort.signal) => {const result = node('button', className, label); result.type='button'; listen(result, 'click', action, signal); return result;};
  const amount = value => typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2}) : '暂无数据';
  function height() {if(disposed || document.fullscreenElement) return; const value=Math.ceil(shell.getBoundingClientRect().height)+4;
    if(value!==lastHeight){lastHeight=value;send('streamlit:setFrameHeight',{height:value});}}
  function cancelMotion() {animations.forEach(animation => animation.cancel()); animations=[];}
  function motion(slide, direction) {
    cancelMotion(); if(reduced.matches || document.hidden || !onscreen || typeof slide.animate!=='function') return;
    const sign=direction<0?-1:1;
    // Each navigation cancels old work before starting. No spring, stale timer,
    // numeric tween or completion callback can put an earlier page back.
    animations.push(slide.animate([
      {opacity:enhanced?.12:.6, transform:enhanced?`translateX(${sign*72}px) translateZ(-150px) rotateY(${sign*-11}deg)`:`translateX(${sign*14}px)`},
      {opacity:1, transform:'translateX(0px) translateZ(0px) rotateY(0deg)'}
    ], {duration:enhanced?690:240,easing:'cubic-bezier(.16,.72,.18,1)',fill:'none'}));
    if(!enhanced)return;
    [...slide.querySelectorAll('.plane-item')].slice(0,9).forEach((part,index)=>{
      animations.push(part.animate([{opacity:.12,translate:`${sign*(35+index*8)}px ${24+index*3}px ${-30-index*9}px`},{opacity:1,translate:'0px 0px 0px'}],
        {duration:610,delay:index*27,easing:'cubic-bezier(.16,.72,.18,1)',fill:'backwards'}));
    });
    if(!$('focusbar').hidden){animations.push($('focus-fact').animate([
      {transform:`translateX(${sign*-22}px) translateZ(80px) scale(1.055)`,filter:'drop-shadow(0 12px 18px #14243c22)'},
      {transform:'translateX(0px) translateZ(0px) scale(1)',filter:'drop-shadow(0 0px 0px transparent)'}
    ],{duration:650,easing:'cubic-bezier(.16,.72,.18,1)',fill:'none'}));}
  }
  function addSource(parent, source) {parent.append(node('div','metric-source',`${source.identity || '来源待核验'} · ${source.file || '来源未记录'}\n${source.location || '位置未记录'}`));}
  function sourceTable(sources) {
    const list=node('div','source-table');
    if(!sources?.length){list.append(node('p','slide-subtitle','当前未保存可展示的指标来源。退出汇报后，可在工作台补充与核对。'));return list;}
    sources.forEach(source=>{const row=node('div','source-row plane-item'), detail=node('div');
      detail.append(node('p','',source.file),node('small','',source.location));
      row.append(node('strong','',source.label),detail,node('span','source-kind',source.identity));list.append(row);});return list;
  }
  const chapterLabel = (chapter, state) => String(state.index+1).padStart(2,'0')+' / '+chapter.title+(chapter.kind==='metrics'?' · '+(state.fact?.year??chapter.year)+' 年':'');
  function heading(slide, chapter, label) {const title=node('h2','plane-item',chapter.heading);if(chapter.kind==='answer')title.tabIndex=0;slide.append(node('div','slide-label',label),title);}
  function content(chapter, state) {
    const slide=node('article',`slide slide-${chapter.kind}`); slide.setAttribute('aria-label',chapter.title);
    const label=chapterLabel(chapter,state);
    if(chapter.kind==='overview'){
      const grid=node('div','overview-grid'), copy=node('div','overview-copy'), sculpture=node('div','sculpture');
      copy.tabIndex=0;copy.setAttribute('aria-label','企业概览，内容较长时可滚动');copy.append(node('div','slide-label','RESEARCH / PRESENTATION'),node('h1','plane-item',chapter.heading),node('div','slide-rule'),node('p','slide-subtitle plane-item',chapter.body));
      const period=node('div','period-line plane-item');period.append(node('strong','',chapter.period),node('span','',chapter.year_count+' 个接入年度'));copy.append(period);
      copy.append(node('p','identity-note',`${chapter.identity?.label || '来源待核验'} · ${chapter.identity?.coverage_text || ''}\n${chapter.identity?.note || ''}`));
      sculpture.setAttribute('aria-hidden','true');
      const back=node('div','paper-layer paper-back plane-item'), middle=node('div','paper-layer paper-middle plane-item'), front=node('div','paper-layer paper-front plane-item');
      back.append(node('span','paper-tag','QINGMENG / RESEARCH'));front.append(node('span','paper-tag','FROM FACTS TO EVIDENCE'),node('strong','','数据。\n结论。\n依据。'),node('small','','在同一条线上，展开这次研究。'));
      sculpture.append(back,middle,front,node('div','paper-seal','有据\n可循'));grid.append(copy,sculpture);slide.append(grid);
    }else if(chapter.kind==='metrics'){
      const row=state.payload.focus?.rows?.find(item=>item.year===state.focus.year);const shown=row?.metrics||chapter.metrics;
      const ordered=[...shown].sort((a,b)=>Number(b.id===state.focus.metric)-Number(a.id===state.focus.metric));
      heading(slide,chapter,label);const grid=node('div','metric-stage');
      ordered.forEach(metric=>{const card=node('section','metric-sheet plane-item'+(metric.id===state.focus.metric?' is-focused':''));card.dataset.metric=metric.id;card.tabIndex=0;card.setAttribute('aria-label',metric.label+'与来源，内容较长时可滚动');card.append(node('span','metric-identity',metric.source.identity),node('span','metric-name',metric.label));
        const value=node('div','metric-value',amount(metric.value));if(metric.value!==null)value.append(node('span','metric-unit',metric.unit));card.append(value);addSource(card,metric.source);grid.append(card);});
      slide.append(grid,node('p','footnote',(row?.ambiguous??chapter.ambiguous)?'同年度存在多条记录，本页不从中任取一条作为企业结论。':'同一个观察指标，将贯穿年度记录与来源定位。数值始终保留接入值。'));
    }else if(chapter.kind==='annual'){
      const fact=state.fact,metricAt=row=>row.metrics.find(metric=>metric.id===state.focus.metric)||row.metrics[0];
      heading(slide,chapter,label);slide.append(node('p','slide-subtitle',`${fact?.label||'营业收入'} / ${fact?.unit||'亿元'} · 点选年度，带着该年数值继续看出处。`));
      const list=node('div','annual-list'), max=Math.max(1,...chapter.rows.map(row=>Math.abs(metricAt(row).value||0)));
      chapter.rows.forEach(row=>{const metric=metricAt(row),value=metric.value,line=button('','annual-row plane-item'+(state.focus.year===row.year?' is-focused':''),()=>deck.setFocus(state.focus.metric,row.year),stageAbort.signal), track=node('div','annual-bar-track'), bar=node('div','annual-bar'+(value<0?' is-negative':''));
        line.dataset.year=String(row.year);line.setAttribute('aria-label',`${row.year} 年 ${metric.label} ${amount(value)} ${value===null?'':metric.unit}`);line.setAttribute('aria-pressed',String(state.focus.year===row.year));
        bar.style.width=typeof value==='number'?Math.abs(value)/max*100+'%':'0%';track.setAttribute('aria-hidden','true');track.append(bar);
        const number=node('div','annual-amount',amount(value));number.append(node('small','',row.ambiguous?'同年度记录待核对':metric.source.identity));line.append(node('span','annual-year',row.year),track,number);list.append(line);});slide.append(list,node('p','footnote','条形长度按绝对量缩放；负值保留负号，缺失年份不补齐。'));
    }else if(chapter.kind==='sources'){
      heading(slide,chapter,label);const reading=node('div','reading');reading.tabIndex=0;reading.setAttribute('aria-label','来源索引，可滚动');
      if(state.fact){const fact=state.fact,spotlight=node('section','source-spotlight plane-item');spotlight.dataset.metric=fact.id;spotlight.dataset.year=String(fact.year);
        spotlight.append(node('span','source-spotlight-label',`${fact.year} 年 · ${fact.label} · ${fact.source.identity}`),node('h3','',fact.value===null?'该年度暂无可定位的有效数值':fact.source.file),node('strong','source-locator',fact.value===null?'独立定位待补充':fact.source.location),
          node('p','',fact.ambiguous?'同年度多条记录待核对。未选择其中任何一条作为该年结论。':fact.value===null?'该年度没有这一指标的有效数值；不使用相邻年度或其它指标的出处替代。':fact.source.recorded?'这是选中数值保存的文件与定位记录。完整原件请回到工作台核对。':'该数值尚无完整独立定位，请回到工作台补充核验。'));
        reading.append(spotlight);const related=chapter.sources.filter(source=>source.metric===fact.id&&source.year!==fact.year);
        if(related.length)reading.append(node('p','related-source-title','同一指标的其它年度记录'),sourceTable(related));
      }else reading.append(sourceTable(chapter.sources));slide.append(reading);
    }else if(chapter.kind==='answer'||chapter.kind==='report'){
      heading(slide,chapter,label);if(chapter.kind==='answer'){const meta=node('div','answer-meta',`${chapter.status} · 范围：${chapter.scope}\n${chapter.status_detail || '沿用保存答案的原始核验状态。'}`);meta.tabIndex=0;meta.setAttribute('aria-label','保存答案的核验状态与企业范围');slide.append(meta);}
      const reading=node('div','reading');reading.tabIndex=0;reading.setAttribute('aria-label','已有研究全文，可滚动');reading.append(node('p',chapter.kind==='answer'?'answer-copy':'report-copy',chapter.body));
      if(chapter.sources?.length){const sources=node('section','answer-sources');sources.append(node('strong','','这份答案保存的来源'),sourceTable(chapter.sources));reading.append(sources);}slide.append(reading);
    }else if(chapter.kind==='signals'){
      heading(slide,chapter,label);const reading=node('div','reading');reading.tabIndex=0;
      chapter.alerts.forEach((alert,index)=>{const item=node('section','signal plane-item'),body=node('div');body.append(node('h3','',alert.title||'已记录信号'),node('p','',alert.message||'未记录额外说明'),node('small','',`依据：${alert.basis || '未记录'}\n规则：${alert.rule || '未记录'}`));item.append(node('span','',String(index+1).padStart(2,'0')),body);reading.append(item);});slide.append(reading);
    }else{heading(slide,chapter,label);slide.append(node('div','empty-mark','—'),node('p','slide-subtitle',chapter.body));}
    return slide;
  }
  function renderEditor(state) {
    const previous=document.activeElement?.dataset?.focusKey;editorAbort.abort();editorAbort=new AbortController();const list=$('editor-list');list.replaceChildren();
    state.order.forEach((id,index)=>{const chapter=state.payload.chapters.find(item=>item.id===id),row=node('div','editor-row'),check=node('input');
      check.type='checkbox';check.id='chapter-choice-'+id;check.checked=state.selected.includes(id);check.disabled=check.checked&&state.selected.length===1;check.dataset.focusKey='check-'+id;
      const label=node('label','',chapter.title);label.htmlFor=check.id;listen(check,'change',()=>deck.toggle(id),editorAbort.signal);
      const up=button('上移','',()=>deck.move(id,-1),editorAbort.signal),down=button('下移','',()=>deck.move(id,1),editorAbort.signal);up.disabled=index===0;down.disabled=index===state.order.length-1;
      up.setAttribute('aria-label',`上移${chapter.title}`);down.setAttribute('aria-label',`下移${chapter.title}`);up.dataset.focusKey='up-'+id;down.dataset.focusKey='down-'+id;row.append(check,label,up,down);list.append(row);});
    if(previous){[...list.querySelectorAll('[data-focus-key]')].find(item=>item.dataset.focusKey===previous&&!item.disabled)?.focus({preventScroll:true});}
  }
  function paintFocus(state,chapter) {
    const fact=state.fact,active=Boolean(fact&&['metrics','annual','sources'].includes(chapter.kind));
    $('focusbar').hidden=!active;shell.dataset.focus=String(active);focusAbort.abort();focusAbort=new AbortController();
    if(!active)return;
    const oldMetric=document.activeElement?.dataset?.focusMetric,choices=$('metric-choices');choices.replaceChildren();
    state.payload.focus.metrics.forEach(metric=>{const choice=button(metric.label,'metric-choice',()=>deck.setFocus(metric.id,state.focus.year),focusAbort.signal);
      choice.dataset.focusMetric=metric.id;choice.setAttribute('aria-pressed',String(metric.id===state.focus.metric));choices.append(choice);});
    if(oldMetric)[...choices.querySelectorAll('button')].find(choice=>choice.dataset.focusMetric===oldMetric)?.focus({preventScroll:true});
    const selector=$('focus-year');selector.replaceChildren();state.payload.focus.rows.forEach(row=>{const option=node('option','',row.year+' 年');option.value=String(row.year);selector.append(option);});selector.value=String(state.focus.year);
    const value=amount(fact.value);if($('focus-value').textContent!==value)$('focus-value').textContent=value;
    $('focus-unit').textContent=fact.value===null?'':fact.unit;$('focus-label').textContent=fact.year+' 年 · '+fact.label;
    $('focus-origin').textContent=fact.ambiguous?'同年度记录待核对':fact.source.identity;$('focus-fact').setAttribute('aria-label',`${fact.year} 年 ${fact.label} ${value} ${fact.value===null?'':fact.unit}，${fact.source.identity}`);
    $('focus-journey').dataset.chapter=chapter.kind;
  }
  function syncMotion(){cancelMotion();shell.dataset.motion=reduced.matches?'reduced':enhanced?'enhanced':'light';$('motion-mode').disabled=reduced.matches;
    $('motion-mode').textContent=reduced.matches?'减少动态效果':enhanced?'增强动效':'轻量动效';$('motion-mode').setAttribute('aria-pressed',String(!reduced.matches&&enhanced));}
  function paint(state) {
    if(!state.payload||disposed)return;const chapter=state.payload.chapters.find(item=>item.id===state.active);
    shell.dataset.chapter=chapter.kind;paintFocus(state,chapter);
    const nav=$('chapters'),restoreNavFocus=Boolean(document.activeElement?.dataset?.chapterId);navAbort.abort();navAbort=new AbortController();nav.replaceChildren();state.visible.forEach((id,index)=>{const item=state.payload.chapters.find(c=>c.id===id),control=button('','chapter-button',()=>deck.go(id),navAbort.signal);
      control.dataset.chapterId=id;control.append(node('span','',String(index+1).padStart(2,'0')),node('b','',item.title));if(id===state.active)control.setAttribute('aria-current','step');nav.append(control);});
    if(restoreNavFocus)nav.querySelector('[aria-current="step"]')?.focus({preventScroll:true});
    $('chapter-count').textContent=String(state.visible.length).padStart(2,'0');$('position').textContent=String(state.index+1).padStart(2,'0');$('total').textContent='/ '+String(state.visible.length).padStart(2,'0');
    $('identity').textContent=!$('focusbar').hidden?state.fact.source.identity:chapter.identity?.label||'来源待核验';$('status').textContent=chapter.status||'现有研究记录';$('previous').disabled=state.index===0;$('next').disabled=state.index===state.visible.length-1;
    $('announcement').textContent=`第 ${state.index+1} 章，共 ${state.visible.length} 章。${chapter.title}。${chapter.status || ''}`;
    if(state.changed||!$('stage').firstElementChild){cancelMotion();stageAbort.abort();stageAbort=new AbortController();const slide=content(chapter,state);$('stage').replaceChildren(slide);motion(slide,state.direction);}
    else if(chapter.kind!=='overview')$('stage').querySelector('.slide-label').textContent=chapterLabel(chapter,state);
    if(editing)renderEditor(state);height();
  }
  const deck=window.QMDirector.createDeck(paint);
  function editor(value){editing=value;$('editor').hidden=!value;$('configure').setAttribute('aria-expanded',String(value));if(value){cancelMotion();renderEditor(deck.snapshot());$('close-editor').focus({preventScroll:true});}else $('configure').focus({preventScroll:true});}
  async function exit(){if(exiting||disposed||!deck.snapshot().payload)return;const revision=deck.snapshot().payload.revision;exiting=true;cancelMotion();
    if(document.fullscreenElement){try{await document.exitFullscreen();}catch(_){/* Exit still works if fullscreen permission changes. */}}
    if(disposed)return;
    send('streamlit:setComponentValue',{value:{event:'exit',revision,nonce:String(Date.now())},dataType:'json'});
  }
  listen($('configure'),'click',()=>editor(!editing));listen($('close-editor'),'click',()=>editor(false));listen($('reset-order'),'click',()=>deck.reset());
  listen($('focus-year'),'change',()=>deck.setFocus(deck.snapshot().focus.metric,Number($('focus-year').value)));
  listen($('motion-mode'),'click',()=>{enhanced=!enhanced;syncMotion();});syncMotion();
  listen($('previous'),'click',()=>deck.step(-1));listen($('next'),'click',()=>deck.step(1));listen($('exit'),'click',exit);
  $('fullscreen').disabled=!document.fullscreenEnabled;
  if(!document.fullscreenEnabled)$('fullscreen').title='当前浏览器未允许嵌入画布全屏，可使用浏览器全屏功能。';
  listen($('fullscreen'),'click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await shell.requestFullscreen();}catch(_){$('announcement').textContent='浏览器没有允许画布全屏，可使用浏览器全屏功能。';}});
  listen(document,'fullscreenchange',()=>{$('fullscreen').textContent=document.fullscreenElement?'退出全屏':'全屏';height();});
  listen(document,'keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();exit();return;}
    if(editing||event.altKey||event.ctrlKey||event.metaKey||event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
    if(event.key==='ArrowRight'){event.preventDefault();deck.step(1);}else if(event.key==='ArrowLeft'){event.preventDefault();deck.step(-1);}
    else if(event.code==='Space'&&!event.target.closest('button')){event.preventDefault();deck.step(1);}
  });
  listen(window,'message',event=>{if(event.source!==parent||event.data?.type!=='streamlit:render')return;const data=event.data.args?.payload;
    if(!data||data.version!==1||typeof data.revision!=='string')return;
    if(deck.setPayload(data)){$('brand-name').textContent=data.brand||'擎梦数智';if(typeof data.logo==='string'&&/^data:image\/(png|webp);base64,/.test(data.logo)){$('brand-logo').src=data.logo;$('brand-logo').hidden=false;}else{$('brand-logo').hidden=true;}}
  });
  function syncVisibility(){shell.dataset.paused=String(document.hidden||!onscreen);if(document.hidden||!onscreen)cancelMotion();}
  listen(document,'visibilitychange',syncVisibility);listen(reduced,'change',syncMotion);
  const observer=new IntersectionObserver(entries=>{onscreen=entries.some(entry=>entry.isIntersecting);syncVisibility();},{threshold:.01});observer.observe(shell);
  const resize=new ResizeObserver(height);resize.observe(shell);
  function dispose(){if(disposed)return;disposed=true;cancelMotion();deck.dispose();observer.disconnect();resize.disconnect();navAbort.abort();editorAbort.abort();focusAbort.abort();stageAbort.abort();abort.abort();}
  listen(window,'pagehide',dispose);window.__qmDirector={deck,dispose};send('streamlit:componentReady',{apiVersion:1});height();
})();
