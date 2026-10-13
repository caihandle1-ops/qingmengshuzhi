'use strict';
// Real GSAP and MutationObserver: late body, one entrance, quiet mode and disposal.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=file=>fs.readFileSync(path.join(__dirname,'../app',file),'utf8');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function markup(kind,id){return `<section data-sidebar-reveal="${kind}" data-sidebar-reveal-id="${id}"><i class="qm-sidebar-rule" aria-hidden="true"></i><button>原生按钮</button></section>`;}
(async()=>{
 const errors=[],listeners=new Set(),vc=new VirtualConsole();vc.on('jsdomError',err=>errors.push(err.message));
 const dom=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc});
 const win=dom.window,doc=win.document;
 let reduced=false;
 win.matchMedia=()=>({get matches(){return reduced;},addEventListener:(_name,fn)=>listeners.add(fn),removeEventListener:(_name,fn)=>listeners.delete(fn)});
 win.Element.prototype.getBoundingClientRect=()=>({top:10,left:10,right:500,bottom:130,width:490,height:120});
 const inject=()=>{const script=doc.createElement('script');script.textContent=read('workspace_sidebar.js');doc.head.appendChild(script);script.remove();};
 try{
  win.eval(read('vendor/gsap/gsap.min.js'));win.gsap.ticker.sleep();
  doc.body.remove();inject();await wait(25);
  const api=win.QMWorkspaceSidebar;assert.ok(api&&!api.disposed);assert.deepEqual(errors,[],'No null-body observer failure');
  const body=doc.createElement('body');body.innerHTML=markup('history','session-index')+markup('settings','settings-1');doc.documentElement.appendChild(body);await wait(70);
  assert.equal(api.getState().records,2);assert.equal(api.getState().seen,2);assert.equal(api.getState().running,2);
  const section=doc.querySelector('[data-sidebar-reveal="settings"]'),button=section.querySelector('button');
  assert.equal(button.style.transform,'');assert.ok(Number(section.style.getPropertyValue('--sidebar-reveal'))>0);
  inject();assert.equal(win.QMWorkspaceSidebar,api);assert.equal(api.getState().running,2,'Reinjection does not duplicate timelines');
  win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));
  for(const tl of win.gsap.globalTimeline.getChildren(true,false,true))tl.progress(1);
  section.remove();await wait(35);body.insertAdjacentHTML('beforeend',markup('settings','settings-1'));await wait(40);
  assert.equal(api.getState().running,0,'Same opening remount retains final pose');
  assert.equal(doc.querySelector('[data-sidebar-reveal="settings"]').style.getPropertyValue('--sidebar-reveal'),'1');
  doc.querySelector('[data-sidebar-reveal="settings"]').remove();await wait(30);
  body.insertAdjacentHTML('beforeend',markup('settings','settings-2'));await wait(50);
  assert.equal(api.getState().running,1,'A later explicit opening gets one entrance');
  reduced=true;for(const listener of listeners)listener();
  assert.equal(api.getState().running,0);assert.equal(doc.querySelector('[data-sidebar-reveal="settings"]').style.getPropertyValue('--sidebar-reveal'),'1');
  reduced=false;doc.documentElement.dataset.qmMotionMode='research';body.insertAdjacentHTML('beforeend',markup('settings','settings-3'));await wait(40);
  assert.equal(api.getState().running,0,'Research mode leaves complete readable geometry');
  assert.ok([...doc.querySelectorAll('button')].every(el=>el.style.transform===''),'Control hitboxes never animate');
  api.dispose();assert.equal(api.disposed,true);assert.equal(api.getState().records,0);assert.equal(listeners.size,0);
  inject();await wait(40);assert.notEqual(win.QMWorkspaceSidebar,api,'Disposed same-version owner is rebuilt on reinjection');assert.equal(win.QMWorkspaceSidebar.disposed,false);
  win.QMWorkspaceSidebar.dispose();assert.equal(listeners.size,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({real_gsap:true,real_mutation_observer:true,late_body:true,same_opening_no_replay:true,native_controls_stable:true,quiet_mode:true,disposal_reinjection:true}));
 }finally{win.QMWorkspaceSidebar?.dispose();win.gsap?.ticker.sleep();dom.window.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
