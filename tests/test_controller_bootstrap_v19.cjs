'use strict';
// Head injection can precede body creation. Keep real MutationObserver validation
// and bundled GSAP so a null target cannot be concealed by an observer mock.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const cases=[
 {file:'research_desks.js',global:'QMResearchDesks',markup:'<section data-desk-scene="answer" data-desk-id="saved-answer"><b>0.00</b><i aria-hidden="true"></i></section>',active:doc=>doc.querySelector('[data-desk-scene]').style.getPropertyValue('--desk-progress')!==''},
 {file:'verification_hub.js',global:'QMVerificationHub',markup:'<section class="st-key-hub_entry_workspace_feature_0"><i data-hub-entry="workspace_feature_0" data-hub-kind="align" aria-hidden="true"></i><div class="st-key-workspace_feature_0"><button type="button">核验</button></div></section>',active:doc=>doc.querySelector('[data-hub-entry]').style.getPropertyValue('--hub-enter')!==''},
 {file:'archive_gallery.js',global:'QMArchiveGallery',markup:'<section class="st-key-archive_gallery"><div data-archive-record="real-file"><div class="archive-arrival"><div class="archive-parallax"><div class="archive-volume"><div data-archive-face>实际文件.pdf</div></div></div></div></div><span data-archive-commit="saved-1" data-archive-selected="real-file" data-archive-open=""></span></section>',active:(_doc,api)=>api.getState().records===1},
];
async function runCase(spec,disposeBeforeBody){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error.message));
 const dom=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc});
 const win=dom.window,doc=win.document,listeners=new Set(),observations=[];
 win.matchMedia=()=>({matches:false,addEventListener:(_name,fn)=>listeners.add(fn),removeEventListener:(_name,fn)=>listeners.delete(fn)});
 const NativeObserver=win.MutationObserver;
 win.MutationObserver=class extends NativeObserver{
  constructor(fn){super(fn);this.connected=false;observations.push(this);}
  observe(target,options){super.observe(target,options);this.connected=true;}
  disconnect(){super.disconnect();this.connected=false;}
 };
 win.Element.prototype.getBoundingClientRect=()=>({x:20,y:30,left:20,top:30,right:620,bottom:260,width:600,height:230});
 win.eval(read('vendor/gsap/gsap.min.js'));win.gsap.ticker.sleep();
 doc.body.remove();assert.equal(doc.body,null);
 const inject=()=>{const script=doc.createElement('script');script.textContent=read(spec.file);doc.head.appendChild(script);script.remove();};
 try{
  inject();assert.deepEqual(errors,[],spec.file+' must not observe a null body during actual head-script injection');
  const api=win[spec.global];assert.ok(api,spec.file+' publishes its lifecycle before body exists');
  await wait(35);
  if(disposeBeforeBody)api.dispose();
  const body=doc.createElement('body');doc.documentElement.appendChild(body);
  await wait(35);body.innerHTML=spec.markup;
  await wait(90);
  assert.equal(spec.active(doc,api),!disposeBeforeBody,spec.file+' observes later content only while mounted');
  if(disposeBeforeBody){
   assert.equal(listeners.size,0);assert.ok(observations.every(observer=>!observer.connected));
   assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0,'Disposed-before-body starts no animation');
  }else{
   assert.ok(win.gsap.globalTimeline.getChildren(true,true,true).length>0,'Late body starts real GSAP');
   inject();assert.equal(win[spec.global],api,'Repeated bootstrap keeps one owner');
   // A replacing native body still emits to the stable Document observer.
   const next=doc.createElement('body');next.innerHTML=spec.markup.replace('saved-answer','new-answer').replace('workspace_feature_0','workspace_feature_1').replace('workspace_feature_0','workspace_feature_1').replace('workspace_feature_0','workspace_feature_1').replace('saved-1','saved-2');
   doc.documentElement.replaceChild(next,body);await wait(75);
   assert.ok(spec.active(doc,api),'Replacement body is discovered without a timer or controller reinjection');
   api.dispose();assert.equal(listeners.size,0);assert.ok(observations.every(observer=>!observer.connected));
   const late=doc.createElement('section');late.innerHTML=spec.markup;next.appendChild(late);await wait(35);
   assert.equal(late.querySelector('[style]'),null,'Disposal prevents later content decoration');
  }
  assert.deepEqual(errors,[]);
 }finally{win[spec.global]?.dispose();win.gsap.ticker.sleep();dom.window.close();}
}
(async()=>{
 const results=[];
 for(const spec of cases){
  try{await runCase(spec,false);await runCase(spec,true);results.push({file:spec.file,passed:true});}
  catch(error){results.push({file:spec.file,passed:false,error:error.message});}
 }
 console.log(JSON.stringify({real_gsap:true,real_mutation_observer:true,head_script_injection:true,results},null,2));
 assert.ok(results.every(result=>result.passed),'All three controllers survive body-less bootstrap and cleanup');
})().catch(error=>{console.error(error);process.exitCode=1;});
