(() => {
  'use strict';
  const model=window.QMExecutionReplay,reduced=matchMedia('(prefers-reduced-motion: reduce)'),abort=new AbortController();
  const el=id=>document.getElementById(id),shell=el('replay');let onscreen=true,lastHeight=0,disposed=false;
  const send=(type,extra={})=>parent.postMessage({isStreamlitMessage:true,type,...extra},'*');
  const height=()=>{const h=Math.ceil(document.body.getBoundingClientRect().height)+8;if(h!==lastHeight&&!disposed){lastHeight=h;send('streamlit:setFrameHeight',{height:h});}};
  const nodeViews=Object.entries(model.labels).map(([id,label])=>{const li=document.createElement('li'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=label;li.append(strong,small);el('stages').append(li);return{id,li,small};});
  function paint(state){if(!state.data)return;const{data,index,playing,states}=state,final=index===data.events.length,event=data.events[index];
    el('event-count').textContent=data.events.length+' 条实际事件';el('event-index').textContent=final?'终':String(index+1).padStart(2,'0');
    const endLabels={completed:'处理结束',interrupted:'处理未完成',awaiting_input:'等待补充条件',needs_attention:'待进一步处理',running:'当前执行状态'};
    el('event-title').textContent=final?(endLabels[data.status]||'保存的执行状态'):model.labels[event.stage];
    el('event-state').textContent=final?'实际记录摘要':model.statuses[event.status];el('event-detail').textContent=final?data.message:event.detail;
    el('event-time').textContent=final?'见各事件':event.elapsed_ms===null?'未记录':Number(event.elapsed_ms).toLocaleString('zh-CN',{maximumFractionDigits:3})+' ms';
    nodeViews.forEach(view=>{const node=states.find(s=>s.id===view.id);view.li.dataset.status=node.status;view.small.textContent=model.statuses[node.status];view.li.title=node.detail;});
    el('position').max=data.events.length;el('position').value=index;el('position').setAttribute('aria-valuetext',final?'实际结果':'第'+(index+1)+'条事件，'+model.labels[event.stage]);
    el('previous').disabled=index===0;el('next').disabled=final;el('latest').disabled=final;el('play').disabled=reduced.matches;el('play').textContent=playing?'暂停回放':final?'从头回放':'继续回放';
    el('position-label').textContent=final?'正在查看保存的最终状态。':'正在回看第 '+(index+1)+' / '+data.events.length+' 条事件；不重新执行查询。';
    shell.style.setProperty('--position',(index/Math.max(1,data.events.length)*170)+'%');shell.dataset.playing=String(playing);shell.dataset.position=String(index);height();
  }
  const runtime=model.createPlayback({schedule:(fn,ms)=>setTimeout(fn,ms),cancel:clearTimeout,onChange:paint,reduced:()=>reduced.matches,visible:()=>!document.hidden&&onscreen});
  const listen=(target,type,fn)=>target.addEventListener(type,fn,{signal:abort.signal});
  listen(el('play'),'click',()=>runtime.toggle());listen(el('previous'),'click',()=>runtime.seek(runtime.snapshot().index-1));listen(el('next'),'click',()=>runtime.seek(runtime.snapshot().index+1));listen(el('latest'),'click',()=>runtime.seek(runtime.snapshot().data.events.length));listen(el('position'),'input',e=>runtime.seek(Number(e.target.value)));
  listen(document,'visibilitychange',()=>{if(document.hidden)runtime.pause();});listen(reduced,'change',()=>runtime.pause());
  listen(window,'message',event=>{if(event.source!==parent||event.data?.type!=='streamlit:render')return;const preference=event.data.args?.motion;shell.dataset.motion=preference?.version===1&&preference.mode==='presentation'?'presentation':'research';const data=event.data.args?.payload;if(!data||!Array.isArray(data.events)||!data.events.length||!Array.isArray(data.stages)||data.stages.length!==4)return;if(!data.events.every(e=>model.labels[e.stage]&&model.statuses[e.status]))return;if(!data.stages.every((s,i)=>s.id===Object.keys(model.labels)[i]&&model.statuses[s.status]))return;runtime.setData(data);height();});
  const observer=new IntersectionObserver(entries=>{onscreen=entries.some(e=>e.isIntersecting);if(!onscreen)runtime.pause();},{threshold:.01});observer.observe(shell);
  const resize=new ResizeObserver(height);resize.observe(shell);
  function dispose(){if(disposed)return;disposed=true;runtime.dispose();observer.disconnect();resize.disconnect();abort.abort();}
  listen(window,'pagehide',dispose);window.__qmExecutionReplay={runtime,dispose};send('streamlit:componentReady',{apiVersion:1});height();
})();
