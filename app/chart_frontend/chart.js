/* Local chart only. Python is the authority for values and evidence indices. */
(() => {
  const svgNS='http://www.w3.org/2000/svg';
  const shell=document.getElementById('chart-shell'), marks=document.getElementById('marks');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const companyColors=new Map(),palette=['#2454b5','#c04b25','#8052b5','#08766e','#b04f80','#71611d','#346c8f','#6554ca'];
  const companyColor=(company)=>{if(!companyColors.has(company)){const index=companyColors.size;companyColors.set(company,palette[index]||`hsl(${(index*137.508)%360} 60% 35%)`);}return companyColors.get(company);};
  let payload=null, activeMetric=null, selected=null, animation=0, prior=new Map(), priorSlots=[],lastRevision='',positions=new Map(),focusEvents=false;
  const send=(type,data={})=>parent.postMessage({isStreamlitMessage:true,type,...data},'*');
  const make=(tag,attrs,parentNode)=>{const el=document.createElementNS(svgNS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));parentNode.appendChild(el);return el;};
  const format=(value)=>new Intl.NumberFormat('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
  const height=()=>send('streamlit:setFrameHeight',{height:Math.ceil(shell.getBoundingClientRect().height)+8});
  function revealPoint(point){const viewport=document.getElementById('chart-viewport'),chart=document.getElementById('chart'),position=positions.get(point.id);if(!viewport.clientWidth||position===undefined)return;const x=position*chart.getBoundingClientRect().width/800,left=viewport.scrollLeft,right=left+viewport.clientWidth,margin=32;if(x<left+margin||x>right-margin)viewport.scrollLeft=Math.max(0,Math.min(viewport.scrollWidth-viewport.clientWidth,x<left+margin?x-margin:x+margin-viewport.clientWidth));}
  function select(point){
    selected=point;const metric=payload.metrics.find(m=>m.id===point.metric);
    document.getElementById('readout-year').textContent=point.company+' · '+point.year+'年度';
    document.getElementById('readout-value').textContent=format(point.value)+' '+metric.unit;
    document.getElementById('readout-source').textContent=point.source+' · '+point.location;
    const hasSource=Number.isInteger(point.source_index),button=document.getElementById('source-button');button.hidden=!hasSource;
    const status=document.getElementById('readout-status');status.textContent=hasSource?'已关联来源位置':'此数据点未关联可打开的来源';status.dataset.source=hasSource?'available':'missing';
    const position=positions.get(point.id),reference=document.getElementById('selection-line');reference.style.visibility='visible';if(position!==undefined){reference.setAttribute('x1',position);reference.setAttribute('x2',position);}
    for(const mark of marks.querySelectorAll('.mark')){mark.setAttribute('aria-current',String(mark.dataset.point===point.id));mark.classList.toggle('dimmed',mark.dataset.point!==point.id);}
    for(const dot of marks.querySelectorAll('.point-dot'))dot.setAttribute('aria-current',String(dot.dataset.point===point.id));
    for(const year of document.getElementById('grid').querySelectorAll('.year-label'))year.setAttribute('aria-current',String(year.dataset.point===point.id||year.dataset.year===String(point.year)));
    height();
  }
  // Opt-in comparison cards receive deliberate clicks only. Hover and arrow
  // navigation remain local and never rerun the surrounding financial page.
  function commitFocus(point){select(point);if(focusEvents)send('streamlit:setComponentValue',{value:{action:'focus',point_id:point.id,revision:payload.revision,nonce:Date.now()},dataType:'json'});}
  function clearUnavailableFocus(closed=false){selected=null;document.getElementById('readout-year').textContent=closed?'选点已收起':'当前企业与年度';document.getElementById('readout-value').textContent=closed?'选择一个数据点':'暂无数据';document.getElementById('readout-source').textContent=closed?'点击图上数据点或企业卡片，继续查看相应记录。':'所选位置没有保留可绘制数值，其他年度不代替此处。';document.getElementById('readout-status').textContent=closed?'来源入口随选点收起':'缺失值保持空缺';document.getElementById('readout-status').dataset.source='missing';document.getElementById('source-button').hidden=true;document.getElementById('selection-line').style.visibility='hidden';for(const mark of marks.querySelectorAll('.mark')){mark.setAttribute('aria-current','false');mark.classList.toggle('dimmed',false);}for(const dot of marks.querySelectorAll('.point-dot'))dot.setAttribute('aria-current','false');height();}
  function draw(){
    if(!payload)return;
    // Keep the live geometry when another metric is selected mid-transition.
    // Cancelling must not rewind bars to the previous completed result.
    cancelAnimationFrame(animation);animation=0;
    if(!payload.metrics.some(m=>m.id===activeMetric))activeMetric=payload.metrics[0]?.id;
    const metric=payload.metrics.find(m=>m.id===activeMetric), points=payload.points.filter(p=>p.metric===activeMetric);
    if(!metric||!points.length)return;
    const comparisonLine=focusEvents&&payload.mode==='line',years=[...new Set(points.map(p=>p.year))].sort((a,b)=>a-b),companies=[...new Set(points.map(p=>p.company))];
    const legend=document.getElementById('series-legend');legend.replaceChildren();legend.hidden=!comparisonLine;
    if(comparisonLine){for(const company of [...new Set(payload.points.map(p=>p.company))].sort())companyColor(company);for(const company of companies){const item=document.createElement('span'),swatch=document.createElement('span'),label=document.createElement('span');item.setAttribute('class','series-legend-item');item.dataset.company=company;swatch.setAttribute('class','series-legend-swatch');swatch.setAttribute('aria-hidden','true');swatch.style.backgroundColor=companyColor(company);label.textContent=company;item.appendChild(swatch);item.appendChild(label);legend.appendChild(item);}}
    document.getElementById('chart-title').textContent=metric.label+' · '+metric.unit;
    document.getElementById('chart-mode').textContent=payload.mode==='line'?'连续年度趋势':'年度数值对比';
    const tabs=document.getElementById('metric-tabs');tabs.replaceChildren();
    if(payload.metrics.length>1)for(const m of payload.metrics){const b=document.createElement('button');b.textContent=m.label;b.setAttribute('aria-pressed',String(m.id===activeMetric));b.addEventListener('click',()=>{activeMetric=m.id;draw();});tabs.appendChild(b);}
    const grid=document.getElementById('grid');grid.replaceChildren();marks.replaceChildren();
    const high=Math.max(0,...points.map(p=>p.value)),low=Math.min(0,...points.map(p=>p.value));
    const spread=(high-low)||1, top=high>0?high+spread*.18:(low===0?1:0),bottom=low<0?low-spread*.08:0;
    const y=(v)=>225-(v-bottom)/(top-bottom)*200,baseline=y(0),step=690/(comparisonLine?years.length:points.length);
    for(let i=0;i<4;i++){const v=bottom+(top-bottom)*i/3;make('line',{x1:70,x2:780,y1:y(v),y2:y(v),class:'grid-line'},grid);const label=make('text',{x:60,y:y(v)+4,'text-anchor':'end',class:'tick'},grid);label.textContent=new Intl.NumberFormat('zh-CN',{maximumFractionDigits:0,notation:Math.abs(v)>=100000?'compact':'standard'}).format(v);}
    const targets=[],seriesPaths=new Map();positions=new Map();
    if(comparisonLine){for(const company of companies){const path=make('path',{fill:'none',stroke:companyColor(company),class:'comparison-series-line'},marks);path.dataset.company=company;seriesPaths.set(company,path);}for(const [index,yearValue] of years.entries()){const label=make('text',{x:70+step*(index+.5),y:255,'text-anchor':'middle',class:'tick year-label'},grid);label.dataset.year=String(yearValue);label.textContent=yearValue+'年';}}
    points.forEach((p,i)=>{
      const x=70+step*((comparisonLine?years.indexOf(p.year):i)+.5),barWidth=Math.min(76,step*.55),target={x,y:y(p.value),height:Math.abs(y(p.value)-baseline),base:baseline};
      positions.set(p.id,x);
      const old=prior.get(p.id)||priorSlots[i]||{...target,y:baseline,height:0};
      const group=make('g',{},marks),bar=make(comparisonLine?'circle':'rect',{...(comparisonLine?{cx:x,cy:target.y,r:11,fill:'transparent'}:{x:x-barWidth/2,y:Math.min(baseline,target.y),width:barWidth,height:target.height,rx:5,fill:p.year===payload.target_year?'#d66032':'#2454b5'}),class:'mark',tabindex:0,role:'button','aria-label':p.company+' '+p.year+'年 '+metric.label+' '+format(p.value)+' '+metric.unit},group);
      bar.dataset.point=p.id;bar.addEventListener('pointerenter',()=>select(p));bar.addEventListener('focus',()=>{select(p);revealPoint(p);});bar.addEventListener('click',()=>commitFocus(p));bar.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();commitFocus(p);}else if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,i+(e.key==='ArrowRight'?1:-1)));marks.querySelectorAll('.mark')[next]?.focus({preventScroll:true});}});
      const tooltip=make('title',{},bar);tooltip.textContent=p.company+' · '+p.year+'年 '+metric.label+' '+format(p.value)+' '+metric.unit;
      const dot=make('circle',{cx:x,cy:target.y,r:5,fill:comparisonLine?companyColor(p.company):'#08766e',class:'point-dot'},group);dot.dataset.point=p.id;dot.addEventListener('pointerenter',()=>select(p));dot.addEventListener('click',()=>commitFocus(p));
      const value=make('text',{x,y:target.y+(p.value>=0?-12:21),'text-anchor':'middle',class:'value-label'},group);value.textContent=format(p.value);
      if(comparisonLine)value.style.fill=companyColor(p.company);
      if(!comparisonLine){const year=make('text',{x,y:255,'text-anchor':'middle',class:'tick year-label'},grid);year.dataset.point=p.id;year.textContent=String(p.year)+(points.some(q=>q.year===p.year&&q.company!==p.company)?' · '+p.company.replace('股份有限公司','').slice(0,6):'年');}
      targets.push({p,bar,dot,value,old,target,index:i});
    });
    const start=performance.now(),line=document.getElementById('line'),isLine=payload.mode==='line';
    const duration=620,stagger=32,maximumDelay=Math.min(160,(targets.length-1)*stagger);
    function frame(now){const immediate=reduced.matches||document.hidden,elapsed=now-start,
      progress=immediate?1:Math.min(1,Math.max(0,elapsed/(duration+maximumDelay))),coords=[],live=[];let previous=null;
      for(const {p,bar,dot,value,old,target,index} of targets){
        const t=immediate?1:Math.min(1,Math.max(0,(elapsed-Math.min(160,index*stagger))/duration)),ease=1-Math.pow(1-t,4),
          cy=old.y+(target.y-old.y)*ease,cx=old.x+(target.x-old.x)*ease,base=old.base+(target.base-old.base)*ease;
        if(comparisonLine){bar.setAttribute('cx',cx);bar.setAttribute('cy',cy);bar.style.opacity='1';}else{bar.setAttribute('x',cx-Number(bar.getAttribute('width'))/2);bar.setAttribute('y',Math.min(base,cy));bar.setAttribute('height',Math.abs(cy-base));bar.style.opacity=isLine?String(.16*(1-ease)):'1';}
        dot.setAttribute('cx',cx);dot.setAttribute('cy',cy);dot.style.opacity=isLine?String(ease):'0';
        value.setAttribute('x',cx);value.setAttribute('y',cy+(p.value>=0?-12:21));
        const join=previous&&previous.company===p.company&&p.year-previous.year===1;coords.push((join?'L':'M')+cx+','+cy);previous=p;
        live.push({x:cx,y:cy,height:Math.abs(cy-base),base});
        if(selected?.id===p.id){const reference=document.getElementById('selection-line');reference.setAttribute('x1',cx);reference.setAttribute('x2',cx);}
      }
      if(comparisonLine){const series=new Map();targets.forEach(({p},i)=>{if(!series.has(p.company))series.set(p.company,[]);series.get(p.company).push({p,position:live[i]});});for(const [company,observations] of series){const pathCoords=[];let before=null;for(const {p,position} of observations.sort((a,b)=>a.p.year-b.p.year)){pathCoords.push((before&&p.year-before.year===1?'L':'M')+position.x+','+position.y);before=p;}seriesPaths.get(company).setAttribute('d',pathCoords.join(' '));seriesPaths.get(company).style.opacity=String(progress);}}
      line.setAttribute('d',comparisonLine?'':coords.join(' '));line.style.opacity=isLine&&!comparisonLine?String(progress):'0';
      prior=new Map(targets.map((target,i)=>[target.p.id,live[i]]));priorSlots=live;
      shell.dataset.chartPhase=progress===1?'settled':'morphing';if(progress<1)animation=requestAnimationFrame(frame);else animation=0;}
    animation=requestAnimationFrame(frame);
    select(points.find(p=>p.id===selected?.id)||points.find(p=>p.year===payload.target_year)||points[points.length-1]);
  }
  document.getElementById('source-button').addEventListener('click',()=>{
    if(!Number.isInteger(selected?.source_index))return;
    // A presentation-only rectangle travels separately from the unchanged,
    // revision-checked source event. No source content is copied to the parent.
    const point=Array.from(marks.querySelectorAll('.mark')).find(mark=>mark.dataset.point===selected.id);
    const pointBox=point?.getBoundingClientRect(),button=document.getElementById('source-button');
    const origin=pointBox&&pointBox.width>0&&pointBox.height>0&&pointBox.left>=0&&pointBox.top>=0&&pointBox.right<=innerWidth&&pointBox.bottom<=innerHeight?pointBox:button.getBoundingClientRect();
    parent.postMessage({type:'qm:evidence-anchor',version:1,rect:{left:origin.left,top:origin.top,width:origin.width,height:origin.height}},'*');
    send('streamlit:setComponentValue',{value:{action:'source',index:selected.source_index,revision:payload.revision,nonce:Date.now()},dataType:'json'});
  });
  window.addEventListener('message',event=>{if(event.source!==parent||event.data?.type!=='streamlit:render')return;const args=event.data.args,next=args.payload;if(!next)return;focusEvents=args.focus_events===true;if(next.revision!==lastRevision){payload=next;lastRevision=next.revision;draw();}const focus=payload.points.find(p=>p.id===args.focus_point);if(focus){if(activeMetric!==focus.metric){activeMetric=focus.metric;draw();}select(focus);}else if(focusEvents)clearUnavailableFocus(args.focus_point==null);const index=args.source_highlight;if(Number.isInteger(index)){const point=payload.points.find(p=>p.source_index===index);if(point){if(activeMetric!==point.metric){activeMetric=point.metric;draw();}select(point);}}});
  const settle=()=>{if(payload&&(document.hidden||reduced.matches)){cancelAnimationFrame(animation);draw();}};
  document.addEventListener('visibilitychange',settle);reduced.addEventListener('change',settle);
  window.addEventListener('pagehide',()=>cancelAnimationFrame(animation));new ResizeObserver(height).observe(shell);
  send('streamlit:componentReady',{apiVersion:1});height();
})();
