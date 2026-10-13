/* Local chart only. Python is the authority for values and evidence indices. */
(() => {
  const svgNS='http://www.w3.org/2000/svg';
  const shell=document.getElementById('chart-shell'),marks=document.getElementById('marks'),viewport=document.getElementById('chart-viewport'),chart=document.getElementById('chart');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let presentation=false,disposed=false;const quiet=()=>!presentation||reduced.matches;
  const abort=new AbortController(),listen=(node,type,handler)=>node.addEventListener(type,handler,{signal:abort.signal});
  const companyColors=new Map(),palette=['#3151f4','#bc4b25','#8052b5','#08766e','#b04f80','#71611d','#346c8f','#6554ca'];
  const companyColor=(company)=>{if(!companyColors.has(company)){const index=companyColors.size;companyColors.set(company,palette[index]||`hsl(${(index*137.508)%360} 60% 35%)`);}return companyColors.get(company);};
  let payload=null,activeMetric=null,selected=null,lastRevision='',positions=new Map(),focusEvents=false,sourceRequest=0,chartWidth=800,animation=null,cursorTween=null,hasRevealed=false,lastWidth=0;
  let drawSignature='',segmentWidth=0,switchContext=null,onScreen=true;
  const switchBand=document.getElementById('chart-turn-band'),switchTrace=document.getElementById('chart-turn-trace');
  function settleSwitch(){const context=switchContext;switchContext=null;context?.revert();shell.dataset.chartTransition='settled';}
  function revealSwitch(){
    if(!switchBand||!switchTrace||!window.gsap||quiet()||document.hidden||!onScreen||disposed)return;
    const context=window.gsap.context(()=>{},shell);switchContext=context;shell.dataset.chartTransition='turning';
    // The paper registration strip is outside the SVG. Every financial mark
    // has its final geometry and remains readable throughout this transition.
    context.add(()=>window.gsap.timeline({defaults:{ease:'power3.inOut'},onComplete:()=>{if(switchContext===context)settleSwitch();}})
      .addLabel('pass').fromTo(switchBand,{xPercent:-110,opacity:1},{xPercent:110,duration:.88},'pass')
      .fromTo(switchTrace,{xPercent:-110,opacity:1},{xPercent:110,duration:.72},'pass+=.11'));
  }
  const send=(type,data={})=>parent.postMessage({isStreamlitMessage:true,type,...data},'*');
  const make=(tag,attrs,parentNode)=>{const el=document.createElementNS(svgNS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));parentNode.appendChild(el);return el;};
  const format=(value)=>new Intl.NumberFormat('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
  const height=()=>send('streamlit:setFrameHeight',{height:Math.ceil(shell.getBoundingClientRect().height)+8});
  function revealPoint(point){const position=positions.get(point.id);if(!viewport.clientWidth||position===undefined)return;const x=position*chart.getBoundingClientRect().width/chartWidth,left=viewport.scrollLeft,right=left+viewport.clientWidth,margin=32;if(x<left+margin||x>right-margin)viewport.scrollLeft=Math.max(0,Math.min(viewport.scrollWidth-viewport.clientWidth,x<left+margin?x-margin:x+margin-viewport.clientWidth));}
  function select(point,immediate=false){
    selected=point;const metric=payload.metrics.find(m=>m.id===point.metric);
    document.getElementById('readout-year').textContent=point.company+' · '+point.year+'年度';
    document.getElementById('readout-value').textContent=format(point.value)+' '+metric.unit;
    document.getElementById('readout-source').textContent=point.source+' · '+point.location;
    const hasSource=Number.isInteger(point.source_index),button=document.getElementById('source-button');button.hidden=!hasSource;
    const status=document.getElementById('readout-status');status.textContent=hasSource?'已关联来源位置':'此数据点未关联可打开的来源';status.dataset.source=hasSource?'available':'missing';
    const position=positions.get(point.id),reference=document.getElementById('selection-line');reference.style.visibility='visible';
    const band=document.getElementById('selection-band');
    if(band&&position!==undefined){band.setAttribute('x',position-segmentWidth/2);band.setAttribute('width',segmentWidth);band.style.visibility='visible';band.dataset.year=String(point.year);band.dataset.point=point.id;}
    if(position!==undefined){cursorTween?.kill();if(window.gsap&&!quiet()&&!immediate)cursorTween=window.gsap.to(reference,{attr:{x1:position,x2:position},duration:.32,ease:'power3.out',overwrite:true});else{reference.setAttribute('x1',position);reference.setAttribute('x2',position);}}
    for(const mark of marks.querySelectorAll('.mark'))mark.setAttribute('aria-current',String(mark.dataset.point===point.id));
    for(const node of [...marks.querySelectorAll('.point-dot'),...marks.querySelectorAll('.chart-bar'),...marks.querySelectorAll('.value-label')])node.setAttribute('aria-current',String(node.dataset.point===point.id));
    for(const year of document.getElementById('grid').querySelectorAll('.year-label'))year.setAttribute('aria-current',String(year.dataset.point===point.id||year.dataset.year===String(point.year)));
    height();
  }
  // Hover, focus and arrow navigation remain local. Only an intentional
  // click/Enter in an opt-in comparison sends an exact point to Python.
  function commitFocus(point){select(point);if(focusEvents)send('streamlit:setComponentValue',{value:{action:'focus',point_id:point.id,revision:payload.revision,nonce:Date.now()},dataType:'json'});}
  function clearUnavailableFocus(closed=false){selected=null;cursorTween?.kill();document.getElementById('readout-year').textContent=closed?'选点已收起':'当前企业与年度';document.getElementById('readout-value').textContent=closed?'选择一个数据点':'暂无数据';document.getElementById('readout-source').textContent=closed?'点击图上数据点或企业卡片，继续查看相应记录。':'所选位置没有保留可绘制数值，其他年度不代替此处。';document.getElementById('readout-status').textContent=closed?'来源入口随选点收起':'缺失值保持空缺';document.getElementById('readout-status').dataset.source='missing';document.getElementById('source-button').hidden=true;document.getElementById('selection-line').style.visibility='hidden';const band=document.getElementById('selection-band');if(band)band.style.visibility='hidden';for(const selector of ['.mark','.point-dot','.chart-bar','.value-label'])for(const node of marks.querySelectorAll(selector))node.setAttribute('aria-current','false');height();}
  function draw(settle=false){
    if(!payload||disposed)return;
    animation?.kill();animation=null;cursorTween?.kill();cursorTween=null;settleSwitch();
    if(!payload.metrics.some(m=>m.id===activeMetric))activeMetric=payload.metrics[0]?.id;
    const metric=payload.metrics.find(m=>m.id===activeMetric),points=payload.points.filter(p=>p.metric===activeMetric);
    if(!metric||!points.length)return;
    const signature=activeMetric+'|'+payload.mode,changed=Boolean(drawSignature&&drawSignature!==signature);drawSignature=signature;
    const comparisonLine=focusEvents&&payload.mode==='line',years=[...new Set(points.map(p=>p.year))].sort((a,b)=>a-b),companies=[...new Set(points.map(p=>p.company))];
    const legend=document.getElementById('series-legend');legend.replaceChildren();legend.hidden=!comparisonLine;
    if(comparisonLine){for(const company of [...new Set(payload.points.map(p=>p.company))].sort())companyColor(company);for(const company of companies){const item=document.createElement('span'),swatch=document.createElement('span'),label=document.createElement('span');item.setAttribute('class','series-legend-item');item.dataset.company=company;swatch.setAttribute('class','series-legend-swatch');swatch.setAttribute('aria-hidden','true');swatch.style.backgroundColor=companyColor(company);label.textContent=company;item.appendChild(swatch);item.appendChild(label);legend.appendChild(item);}}
    document.getElementById('chart-title').textContent=metric.label+' · '+metric.unit;
    document.getElementById('chart-mode').textContent=payload.mode==='line'?'连续年度趋势':'年度数值对比';
    shell.dataset.mode=payload.mode;shell.classList.toggle('dense-labels',points.length>8);
    const tabs=document.getElementById('metric-tabs');tabs.replaceChildren();
    if(payload.metrics.length>1)for(const m of payload.metrics){const b=document.createElement('button');b.textContent=m.label;b.setAttribute('aria-pressed',String(m.id===activeMetric));b.addEventListener('click',()=>{activeMetric=m.id;draw(true);});tabs.appendChild(b);}
    const grid=document.getElementById('grid');grid.replaceChildren();marks.replaceChildren();
    // Financial geometry is final from the first painted frame. Only line
    // dashes / opacity reveal; there are no interpolated financial values.
    chartWidth=Math.max(620,Math.round(viewport.clientWidth||800));lastWidth=Math.round(viewport.clientWidth||800);
    chart.setAttribute('viewBox',`0 0 ${chartWidth} 300`);
    const high=Math.max(0,...points.map(p=>p.value)),low=Math.min(0,...points.map(p=>p.value));
    const spread=(high-low)||1,top=high>0?high+spread*.2:(low===0?1:0),bottom=low<0?low-spread*.12:0;
    const y=(v)=>240-(v-bottom)/(top-bottom)*208,baseline=y(0),step=(chartWidth-104)/(comparisonLine?years.length:points.length);
    segmentWidth=Math.max(1,step-8);
    for(let i=0;i<4;i++){const v=bottom+(top-bottom)*i/3;make('line',{x1:72,x2:chartWidth-24,y1:y(v),y2:y(v),class:'grid-line'},grid);const label=make('text',{x:60,y:y(v)+4,'text-anchor':'end',class:'tick'},grid);label.textContent=new Intl.NumberFormat('zh-CN',{maximumFractionDigits:Math.max(Math.abs(bottom),Math.abs(top))<2?1:0,notation:Math.abs(v)>=100000?'compact':'standard'}).format(v);}
    if(low<0)make('line',{x1:72,x2:chartWidth-24,y1:baseline,y2:baseline,class:'zero-line'},grid);
    const targets=[],seriesPaths=new Map(),line=document.getElementById('line'),coords=[];let previous=null;positions=new Map();
    const reference=document.getElementById('selection-line');reference.setAttribute('y1',24);reference.setAttribute('y2',248);
    if(comparisonLine){for(const company of companies){const path=make('path',{fill:'none',stroke:companyColor(company),class:'comparison-series-line'},marks);path.dataset.company=company;seriesPaths.set(company,path);}for(const [index,yearValue] of years.entries()){const label=make('text',{x:72+step*(index+.5),y:275,'text-anchor':'middle',class:'tick year-label'},grid);label.dataset.year=String(yearValue);label.textContent=yearValue+'年';}}
    points.forEach((p,i)=>{
      const x=72+step*((comparisonLine?years.indexOf(p.year):i)+.5),cy=y(p.value),barWidth=Math.min(82,step*.42);
      positions.set(p.id,x);
      const group=make('g',{},marks),bar=make('rect',{x:x-barWidth/2,y:Math.min(baseline,cy),width:barWidth,height:Math.abs(cy-baseline),rx:2,fill:p.year===payload.target_year?'#3151f4':'#a9b8ff',class:'chart-bar'},group);bar.dataset.point=p.id;
      const dot=make('circle',{cx:x,cy,r:5.5,fill:comparisonLine?companyColor(p.company):'#3151f4',class:'point-dot'},group);dot.dataset.point=p.id;
      const value=make('text',{x,y:cy+(p.value>=0?-17:23),'text-anchor':'middle',class:'value-label'},group);value.textContent=format(p.value);value.dataset.point=p.id;
      if(comparisonLine)value.style.fill=companyColor(p.company);
      // Hit geometry is separate: a real zero stays zero-height and remains
      // selectable by mouse and keyboard without inventing a visible bar.
      const hit=make(comparisonLine?'circle':'rect',{...(comparisonLine?{cx:x,cy,r:13}:{x:x-Math.max(24,barWidth)/2,y:Math.min(baseline,cy)-10,width:Math.max(24,barWidth),height:Math.max(24,Math.abs(cy-baseline)+20)}),fill:'transparent',class:'mark',tabindex:0,role:'button','aria-label':p.company+' '+p.year+'年 '+metric.label+' '+format(p.value)+' '+metric.unit},group);
      hit.dataset.point=p.id;hit.addEventListener('pointerenter',()=>select(p));hit.addEventListener('focus',()=>{select(p);revealPoint(p);});hit.addEventListener('click',()=>commitFocus(p));hit.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();commitFocus(p);}else if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,i+(e.key==='ArrowRight'?1:-1)));marks.querySelectorAll('.mark')[next]?.focus({preventScroll:true});}});
      const tooltip=make('title',{},hit);tooltip.textContent=p.company+' · '+p.year+'年 '+metric.label+' '+format(p.value)+' '+metric.unit;
      if(!comparisonLine){const year=make('text',{x,y:275,'text-anchor':'middle',class:'tick year-label'},grid);year.dataset.point=p.id;year.textContent=String(p.year)+(points.some(q=>q.year===p.year&&q.company!==p.company)?' · '+p.company.replace('股份有限公司','').slice(0,6):'年');}
      const join=previous&&previous.company===p.company&&p.year-previous.year===1;coords.push((join?'L':'M')+x+','+cy);previous=p;
      targets.push({p,x,y:cy,bar,dot,value});
    });
    if(comparisonLine){for(const [company,path] of seriesPaths){const series=targets.filter(item=>item.p.company===company).sort((a,b)=>a.p.year-b.p.year);let before=null;const pathCoords=[];for(const item of series){pathCoords.push((before&&item.p.year-before.year===1?'L':'M')+item.x+','+item.y);before=item.p;}path.setAttribute('d',pathCoords.join(' '));}}
    line.setAttribute('d',comparisonLine?'':coords.join(' '));line.style.opacity=payload.mode==='line'&&!comparisonLine?'1':'0';line.style.strokeDasharray='none';line.style.strokeDashoffset='0';
    shell.dataset.chartPhase='settled';
    const paths=comparisonLine?[...seriesPaths.values()]:payload.mode==='line'?[line]:[];
    if(!hasRevealed&&!settle&&!quiet()&&!document.hidden&&window.gsap){
      shell.dataset.chartPhase='revealing';
      animation=window.gsap.timeline({onComplete:()=>{shell.dataset.chartPhase='settled';animation=null;}});
      for(const path of paths){const length=path.getTotalLength?.()||0;if(length){path.style.strokeDasharray=String(length);animation.fromTo(path,{strokeDashoffset:length},{strokeDashoffset:0,duration:1.05,ease:'power3.inOut',onComplete:()=>{path.style.strokeDasharray='none';}},0);}}
      animation.fromTo(targets.map(item=>payload.mode==='line'?item.dot:item.bar),{opacity:0},{opacity:1,duration:.38,stagger:.07,ease:'power2.out'},.15);
    }
    hasRevealed=true;
    if(changed)revealSwitch();
    select(points.find(p=>p.id===selected?.id)||points.find(p=>p.year===payload.target_year)||points[points.length-1],true);height();
  }
  listen(document.getElementById('source-button'),'click',()=>{
    if(!Number.isInteger(selected?.source_index))return;
    const point=Array.from(marks.querySelectorAll('.mark')).find(mark=>mark.dataset.point===selected.id);
    const pointBox=point?.getBoundingClientRect(),button=document.getElementById('source-button');
    const origin=pointBox&&pointBox.width>0&&pointBox.height>0&&pointBox.left>=0&&pointBox.top>=0&&pointBox.right<=innerWidth&&pointBox.bottom<=innerHeight?pointBox:button.getBoundingClientRect();
    parent.postMessage({type:'qm:evidence-anchor',version:1,rect:{left:origin.left,top:origin.top,width:origin.width,height:origin.height}},'*');
    send('streamlit:setComponentValue',{value:{action:'source',index:selected.source_index,point_id:selected.id,source_id:selected.source_id,revision:payload.revision,nonce:String(Date.now())+'-'+(++sourceRequest)},dataType:'json'});
  });
  listen(window,'message',event=>{if(event.source!==parent||event.data?.type!=='streamlit:render')return;const args=event.data.args||{},next=args.payload;if(!next)return;const nextMode=args.motion?.version===1&&args.motion.mode==='presentation',modeChanged=nextMode!==presentation;presentation=nextMode;shell.dataset.appearance=args.appearance==='cockpit'?'cockpit':'standard';if(modeChanged&&payload)draw(true);focusEvents=args.focus_events===true;if(next.revision!==lastRevision){payload=next;lastRevision=next.revision;draw();}const focus=payload.points.find(p=>p.id===args.focus_point);if(focus){if(activeMetric!==focus.metric){activeMetric=focus.metric;draw(true);}select(focus,true);}else if(focusEvents)clearUnavailableFocus(args.focus_point==null);const index=args.source_highlight;if(Number.isInteger(index)){const point=payload.points.find(p=>p.source_index===index);if(point){if(activeMetric!==point.metric){activeMetric=point.metric;draw(true);}select(point,true);}}});
  const settle=()=>{if(payload&&(document.hidden||quiet()))draw(true);};
  listen(document,'visibilitychange',settle);listen(reduced,'change',settle);
  const resize=new ResizeObserver(()=>{const width=Math.round(viewport.clientWidth||800);if(payload&&width!==lastWidth)draw(true);height();});resize.observe(shell);
  const intersection=window.IntersectionObserver?new IntersectionObserver(entries=>{onScreen=entries.some(entry=>entry.isIntersecting);if(!onScreen)settleSwitch();},{threshold:0}):null;intersection?.observe(shell);
  function dispose(){if(disposed)return;disposed=true;settleSwitch();animation?.kill();cursorTween?.kill();animation=null;cursorTween=null;resize.disconnect();intersection?.disconnect();abort.abort();}
  listen(window,'pagehide',dispose);window.__qmChart={dispose};
  send('streamlit:componentReady',{apiVersion:1});height();
})();
