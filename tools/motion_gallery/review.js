'use strict';
const frame=document.getElementById('review-frame'),scene=document.getElementById('scene'),mode=document.getElementById('mode'),viewport=document.getElementById('viewport');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
function payload(){return {type:'gallery:view',scene:scene.value,mode:mode.value};}
function update(){const [width,height]=viewport.value.split('x');frame.width=width;frame.height=height;document.getElementById('case-label').textContent=`${viewport.value} / ${reduced.matches?'os-reduced':mode.value} / ${scene.value} · 待观察`;frame.contentWindow.postMessage(payload(),location.origin);}
for(const control of [scene,mode,viewport])control.addEventListener('change',update);
reduced.addEventListener('change',update);
frame.addEventListener('load',update);
document.getElementById('remount').addEventListener('click',()=>frame.contentWindow.postMessage({type:'gallery:remount'},location.origin));
document.getElementById('inspect').addEventListener('click',()=>frame.contentWindow.postMessage({type:'gallery:inspect'},location.origin));
window.addEventListener('message',event=>{if(event.source!==frame.contentWindow||event.origin!==location.origin)return;if(event.data?.type==='gallery:ready')update();if(event.data?.type==='gallery:state'){document.getElementById('runtime-state').textContent=JSON.stringify(event.data.state,null,2);document.querySelector('details').open=true;}});
update();
