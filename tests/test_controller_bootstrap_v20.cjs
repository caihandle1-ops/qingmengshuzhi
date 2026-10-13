'use strict';
// All sixteen affected entry points use actual script injection and native
// MutationObserver validation. GSAP is the pinned production build; geometry,
// IntersectionObserver and ResizeObserver are controlled (no pixel/FPS claim).
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const cases=[
 ['asset_gallery_motion.js','__qmAssetGallery','<section class="st-key-asset_gallery"><span data-asset-gallery-commit="first"></span></section>'],
 ['command_palette.js','QMCommandPalette','<div class="st-key-workspace_search_open_button"><button>搜索</button></div>',d=>d.querySelector('button').getAttribute('aria-keyshortcuts')==='Control+k Meta+k'],
 ['content_motion.js','QMContentMotion','<section data-qm-content="answer" data-qm-content-key="first"><p data-qm-content-part="body">确认内容 123.45</p></section>',(_d,a)=>a.getState().roots===1],
 ['enterprise_story.js','__qmEnterpriseStory','<section data-enterprise-story="actual"><div data-es-chapter><i class="es-chapter-rule"></i></div><div data-es-pane></div><span class="es-current-chapter"></span><span class="es-stage-count"></span></section>',d=>d.querySelector('[data-enterprise-story]').classList.contains('is-enhanced')],
 ['evidence_lens.js','QMEvidenceLens','<section data-evidence-lens="source"><div data-el-surface><pre>原件 0</pre><div data-el-cover>原文</div><i data-el-rim></i></div><button data-el-toggle>展开</button></section>',(_d,a)=>a.getState().length===1],
 ['evidence_motion.js','__qmEvidenceStage','<section class="st-key-answer_sources_panel_test">已授权原文</section>'],
 ['feature_workflow.js','QMFeatureWorkflow','<div class="st-key-qa_composer"><div class="st-key-qa_submit"><button>分析</button></div></div>',(_d,a)=>a.getState().hosts===1],
 ['metric_journey.js','__qmMetricJourney','<div data-metric-journey="first"><i aria-hidden="true"></i></div>'],
 ['motion.js','__qingmengMotion','<section class="st-key-workspace_context_panel">研究上下文</section>'],
 ['probe_visual.js','__qmProbeVisual','<section class="qm-probe-visual" data-can-animate="false"></section>',d=>d.querySelector('.qm-probe-visual').dataset.phase==='final'],
 ['reading_position.js','__qmReadingPosition','<main data-testid="stMain"><div data-testid="stMainBlockContainer">原文</div></main>'],
 ['report_reader.js','__qmReportReader','<section data-report-reader><section data-report-chapter="0">报告</section></section>',d=>d.querySelector('[data-report-reader]').style.getPropertyValue('--rr-progress')!==''],
 ['result_continuity.js','QMResultContinuity','<section class="st-key-answer_summary_test"><div class="st-key-answer_canvas_lead_test"><div data-testid="stMetric"><b data-testid="stMetricValue">0</b></div></div><div class="st-key-answer_canvas_research_test">来源</div><div class="st-key-answer_research_toggle_test"><button>展开</button></div><span data-result-continuity="answer" data-result-native-key="test" data-result-expanded="false"></span></section>',(_d,a)=>a.getState().mounted===1],
 ['source_dock.js','__qmSourceDock','<section class="st-key-source_dock_panel_test"><span data-source-dock="test" data-source-dock-panel="source_dock_panel_test" data-source-dock-identity="actual" data-source-dock-kind="research" data-source-dock-close="close_test"></span><div class="st-key-close_test"><button>关闭</button></div></section>'],
 ['studio_motion.js','__qmStudioMotion','<section class="studio-financial-device">装置</section>'],
 ['tool_entries.js','QMToolEntries','<section class="st-key-tool_entry_scope_enter_six"><i data-tool-entry="scope_enter_six" data-tool-kind="align"></i><div class="st-key-scope_enter_six"><button>核验</button></div></section>',(_d,a)=>a.getState().entries===1],
];
async function runCase(spec,disposeBeforeBody){
 const [file,key,markup,active]=spec,errors=[],observations=[],vc=new VirtualConsole();
 vc.on('jsdomError',error=>errors.push(error.message));vc.on('warn',message=>errors.push(String(message)));
 const dom=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc});
 const win=dom.window,doc=win.document;
 win.matchMedia=query=>{const target=new win.EventTarget();target.matches=query.includes('min-width');return target;};
 win.CSS={escape:value=>String(value).replace(/[^\w-]/g,'\\$&')};
 win.Element.prototype.getBoundingClientRect=()=>({x:20,y:30,left:20,top:30,right:620,bottom:260,width:600,height:230});
 win.Element.prototype.scrollIntoView=function(){};
 win.ResizeObserver=class{observe(node){assert.ok(node instanceof win.Element);}unobserve(){}disconnect(){}};
 win.IntersectionObserver=class{observe(node){assert.ok(node instanceof win.Element);}unobserve(){}disconnect(){}};
 const NativeObserver=win.MutationObserver;
 win.MutationObserver=class extends NativeObserver{
  constructor(callback){let record;super((changes,observer)=>{record.deliveries++;callback(changes,observer);});record={observer:this,connected:false,deliveries:0};this.record=record;observations.push(record);}
  observe(target,options){super.observe(target,options);this.record.connected=true;this.record.target=target;}
  disconnect(){super.disconnect();this.record.connected=false;}
 };
 win.eval(read('vendor/gsap/gsap.min.js'));
 doc.body.remove();assert.equal(doc.body,null);
 const inject=()=>{const script=doc.createElement('script');script.textContent=read(file)+'\n//# sourceURL='+file;doc.head.appendChild(script);script.remove();};
 try{
  inject();await wait(45); // A full animation frame before any body exists.
  assert.deepEqual(errors,[],file+' starts without a body');
  const api=win[key];assert.ok(api&&typeof api.dispose==='function',file+' publishes a lifecycle');
  assert.equal(observations.length,1);assert.equal(observations[0].target,doc,'Stable Document owns observation');
  if(disposeBeforeBody)api.dispose();
  const deliveries=observations[0].deliveries;
  const body=doc.createElement('body');body.innerHTML=markup+'<input id="untouched" value="原有输入"/><button id="native">原生操作</button>';
  doc.documentElement.appendChild(body);await wait(65);
  if(disposeBeforeBody){
   assert.equal(observations[0].deliveries,deliveries,'Disposed early controller receives no late-body updates');
   assert.ok(observations.every(record=>!record.connected));
   assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0,'Disposed early owner starts no tween');
  }else{
   assert.ok(observations[0].deliveries>deliveries,'Late body actually reaches the native observer callback');
   if(active)assert.ok(active(doc,api),file+' mounts its late-arriving feature');
   const count=observations.length;inject();await wait(30);
   assert.equal(win[key],api,'Same-version rerun retains one owner');assert.equal(observations.length,count,'No duplicate observer after rerun');
   const replacement=doc.createElement('body');replacement.innerHTML=body.innerHTML;
   const beforeReplacement=observations[0].deliveries;doc.documentElement.replaceChild(replacement,body);await wait(65);
   assert.ok(observations[0].deliveries>beforeReplacement,'Body replacement remains observable');
   if(active)assert.ok(active(doc,api),file+' remounts after body replacement');
   const afterReplacement=observations[0].deliveries;replacement.appendChild(doc.createElement('article'));await wait(35);
   assert.ok(observations[0].deliveries>afterReplacement,'Observer follows descendants of the replacement body');
   const input=doc.getElementById('untouched'),native=doc.getElementById('native');let clicks=0;
   native.addEventListener('click',()=>clicks++);native.click();assert.equal(clicks,1);assert.equal(input.value,'原有输入');assert.equal(native.style.transform,'');
   api.dispose();await wait(25);const afterDispose=observations[0].deliveries;
   replacement.appendChild(doc.createElement('section'));await wait(35);
   assert.equal(observations[0].deliveries,afterDispose,'Disposed controller does not restart on DOM updates');
   assert.ok(observations.every(record=>!record.connected));
   assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0,'Disposal clears actual GSAP work');
  }
  assert.deepEqual(errors,[],file+' has no startup/rerun/lifecycle console error');
 }finally{win[key]?.dispose();win.gsap.ticker.sleep();dom.window.close();}
}
(async()=>{
 const results=[];
 for(const spec of cases){try{await runCase(spec,false);await runCase(spec,true);results.push({file:spec[0],passed:true});}catch(error){results.push({file:spec[0],passed:false,error:error.stack});}}
 console.log(JSON.stringify({real_gsap:true,real_mutation_observer:true,controllers:cases.length,late_body:true,body_replacement:true,same_version_rerun:true,dispose_before_body:true,results},null,2));
 assert.ok(results.every(result=>result.passed),'Every affected controller survives asynchronous document bootstrap');
})().catch(error=>{console.error(error);process.exitCode=1;});
