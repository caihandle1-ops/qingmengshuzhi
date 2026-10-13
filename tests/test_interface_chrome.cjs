'use strict';
// Real bundled GSAP and native events with deterministic geometry, not a pixel/FPS acceptance test.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const markup=`<aside data-testid="stSidebar">
  <div class="st-key-new_session" data-testid="stButton"><button id="new-session">新建会话</button></div>
  <div class="st-key-navigation"><div role="radiogroup"><label><input type="radio" checked>财报问数</label></div></div>
</aside><main data-testid="stMain">
  <section class="st-key-app_header"><div class="st-key-header_bar">
    <div class="st-key-layer_navigation"><div data-testid="stButton"><button id="return">返回上一层</button></div></div>
    <div class="st-key-header_search_desktop"><form>
      <input id="search" value="比亚迪 2024 净利润 -123.45 / 0">
      <div data-testid="stFormSubmitButton"><button id="search-submit">搜索</button></div>
    </form></div>
  </div></section>
  <section class="st-key-answer_actions_7" data-rect="20,200,900,60">
    <div class="st-key-answer_sources_toggle_7" data-testid="stButton"><button id="sources" kind="secondary" data-rect="20,200,400,60">查看来源 · 1份文件</button></div>
    <div class="st-key-answer_verdict_verified_7"><div class="st-key-answer_check_toggle_7" data-testid="stButton"><button id="check" kind="secondary" data-rect="450,200,470,60">核验 · 适用核验完成</button></div></div>
  </section>
  <section class="st-key-source_document_toolbar_abc"><div data-testid="stButton"><button id="preview">收起原文预览</button></div><div data-testid="stDownloadButton"><button id="original">下载原始文件</button></div></section>
  <section class="st-key-publication_toolbar_report"><div data-testid="stButton"><button id="reader" kind="primary">收起阅读全文</button></div><div data-testid="stDownloadButton"><button id="pdf">PDF</button></div><div data-testid="stDownloadButton"><button id="txt" disabled>TXT</button></div></section>
  <section class="st-key-workspace_search_results"><div class="st-key-workspace_search_item_workspace_search_company_0"><span>企业</span><div data-testid="stButton"><button id="result">比亚迪股份有限公司</button></div><span>2024年</span></div></section>
  <section data-testid="stExpander"><details id="details"><summary><div><span><span id="custom-icon" data-testid="stExpanderIcon">keyboard_arrow_right</span></span><div><span>口径计算明细</span><span id="label-icon" data-testid="stIconMaterial">keyboard_arrow_right</span></div><span><span id="native-chevron" data-testid="stIconMaterial" data-qm-ui-chevron="authored">chevron_right</span></span></div></summary><div data-testid="stExpanderDetails"><input id="value" value="-123.45"><p id="figure">0</p></div></details></section>
  <section class="st-key-qa_composer"><div data-testid="stExpander"><details><summary>当前识别条件</summary><div>条件</div></details></div></section>
  <section class="st-key-research_task_strip"><div data-testid="stExpander"><details><summary>研究任务 · 检查点与恢复</summary><div>检查点</div></details></div></section>
  <section class="st-key-workspace_hero"><div data-testid="stExpander"><details><summary>首页说明</summary></details></div></section>
  <section data-testid="stDialog"><div data-testid="stExpander"><details><summary>对话框说明</summary></details></div></section>
  <section data-testid="stExpander"><details><summary><div><span data-testid="stExpanderStepIcon">check_circle</span><span data-testid="stExpanderStepChevron">keyboard_arrow_right</span><span>原生任务状态</span></div></summary></details></section>
  <div data-testid="stButton"><button id="unowned">其他操作</button></div>
</main>`;
const dom=new JSDOM(`<!doctype html><html><body>${markup}</body></html>`,{runScripts:'outside-only',pretendToBeVisual:true});
const win=dom.window,doc=win.document,listeners=new Set(),intersections=[],errors=[];
const media={matches:false,addEventListener:(_,fn)=>listeners.add(fn),removeEventListener:(_,fn)=>listeners.delete(fn)};
const fine={matches:true,addEventListener(){},removeEventListener(){}};
win.matchMedia=query=>query.includes('prefers-reduced-motion')?media:fine;
win.addEventListener('error',event=>errors.push(event.error));
win.IntersectionObserver=class{constructor(fn){this.callback=fn;this.nodes=new Set();intersections.push(this);}observe(node){this.nodes.add(node);}unobserve(node){this.nodes.delete(node);}disconnect(){this.nodes.clear();}};
win.HTMLElement.prototype.getBoundingClientRect=function(){
  const [left,top,width,height]=String(this.dataset.rect||'20,20,300,52').split(',').map(Number);
  return {x:left,y:top,left,top,width,height,right:left+width,bottom:top+height,toJSON(){return this;}};
};
win.HTMLElement.prototype.animate=function(){let done;return {finished:new Promise(resolve=>{done=resolve;win.setTimeout(done,0);}),cancel(){done();}};};
const pointer=(node,name)=>node.dispatchEvent(new win.MouseEvent(name,{bubbles:true,button:0,clientX:70,clientY:70}));
const hover=node=>Number(node.style.getPropertyValue('--qm-ui-hover')||0);
const opened=node=>Number(node.style.getPropertyValue('--qm-ui-open')||0);
const selected=node=>Number(node.querySelector('.qm-ui-active-line').style.opacity||0);
win.eval(read('vendor/gsap/gsap.min.js'));win.eval(read('feature_workflow.js'));
(async()=>{
  await delay(65);
  const api=win.QMFeatureWorkflow,header=doc.querySelector('.st-key-header_search_desktop'),search=doc.querySelector('#search');
  const actions=doc.querySelector('.st-key-answer_actions_7'),sources=doc.querySelector('#sources'),check=doc.querySelector('#check');
  const details=doc.querySelector('#details'),summary=details.querySelector('summary');
  const nativeChevron=doc.querySelector('#native-chevron');
  const originalText=summary.textContent,field=doc.querySelector('#value'),figure=doc.querySelector('#figure');
  const chrome=[...doc.querySelectorAll('#new-session,#return,#search-submit,#sources,#check,#preview,#original,#reader,#pdf,#txt,#result')];
  assert.equal(chrome.every(node=>node.dataset.qmUiButton==='true'),true,'All explicitly named chrome surfaces have one microinteraction owner.');
  assert.equal(doc.querySelector('[role="radiogroup"]').dataset.qmUiGroup,undefined,'Existing sidebar indicator keeps its own owner.');
  assert.equal(doc.querySelector('.st-key-publication_toolbar_report .qm-ui-active-line'),null,'Reader/download toolbar is never treated as a selection group.');
  assert.equal(selected(actions),0,'A verified verdict is not an opened evidence panel.');
  sources.click();await delay(55);assert.equal(selected(actions),0,'Click intent cannot fabricate confirmed panel state.');
  sources.setAttribute('kind','primary');await delay(500);assert.equal(selected(actions),1);
  sources.setAttribute('kind','secondary');check.setAttribute('kind','primary');await delay(85);
  const pose=actions.querySelector('.qm-ui-active-line').style.transform;
  assert.notEqual(pose,'translate(430px, 58px) scaleX(470)','Confirmed selection moves continuously through intermediate geometry.');
  check.setAttribute('kind','secondary');await delay(500);assert.equal(selected(actions),0,'Closing both native panels clears selection.');
  search.focus();await delay(340);assert.equal(Number(header.style.getPropertyValue('--qm-ui-focus')),1);assert.equal(doc.activeElement,search);
  const searchValue=search.value;let submits=0;search.closest('form').addEventListener('submit',event=>{submits++;event.preventDefault();});
  doc.querySelector('#search-submit').click();assert.equal(submits,1,'Native form submission remains intact.');
  const target=doc.querySelector('#result');pointer(target,'pointerover');await delay(65);assert.ok(hover(target)>0&&hover(target)<1);
  for(let index=0;index<12;index++){pointer(target,'pointerout');pointer(target,'pointerover');}
  pointer(target,'pointerout');await delay(350);assert.equal(hover(target),0);assert.equal(api.getState().running,0,'Rapid hover reverses without leaving stale tweens.');
  pointer(doc.querySelector('#txt'),'pointerover');assert.equal(hover(doc.querySelector('#txt')),0,'Disabled download remains visually disabled.');
  assert.equal(search.value,searchValue);assert.equal(doc.activeElement,search);
  assert.equal(api.getState().disclosures,1);assert.equal(doc.querySelectorAll('.qm-ui-expander-mark').length,1,'QA/recovery, home, dialog and status-step fold controls retain their own styling.');
  assert.equal(nativeChevron.dataset.qmUiChevron,'true','The actual native compact toggle icon is identified behind a leading custom icon.');
  assert.equal(doc.querySelector('#custom-icon').dataset.qmUiChevron,undefined,'A custom icon is never hidden, even with the same glyph.');
  assert.equal(doc.querySelector('#label-icon').dataset.qmUiChevron,undefined,'An icon inside the readable label is never hidden.');
  const mark=summary.querySelector('.qm-ui-expander-mark');assert.equal(mark.getAttribute('aria-hidden'),'true');assert.equal(mark.inert,true);assert.equal(mark.textContent,'');
  assert.equal(summary.textContent,originalText,'Disclosure decoration does not duplicate title or financial text.');
  summary.click();assert.equal(details.open,true);await delay(80);assert.ok(opened(summary)>0&&opened(summary)<1);
  summary.click();assert.equal(details.open,false);await delay(55);summary.click();await delay(350);assert.equal(opened(summary),1);
  details.open=false;await delay(350);assert.equal(opened(summary),0,'Actual details.open controls decoration even without a pointer click.');
  assert.equal(summary.style.height,'');assert.equal(details.style.height,'');assert.equal(details.style.transform,'');
  assert.equal(summary.style.transform,'');assert.equal(field.value,'-123.45');assert.equal(figure.textContent,'0');assert.equal(win.gsap.getTweensOf(field).length,0);
  const newChevron=doc.createElement('span');newChevron.dataset.testid='stIconMaterial';newChevron.textContent='keyboard_arrow_down';
  nativeChevron.replaceWith(newChevron);await delay(65);assert.equal(newChevron.dataset.qmUiChevron,'true','React replacing a native icon refreshes the owned marker.');
  assert.equal(nativeChevron.dataset.qmUiChevron,'authored','The replaced icon has its original marker restored.');

  win.eval(read('motion.js'));await delay(65);
  let nativeClicks=0;target.addEventListener('click',()=>nativeClicks++);pointer(target,'pointerdown');pointer(target,'pointermove');target.click();await delay(35);
  assert.equal(nativeClicks,1);assert.equal(doc.querySelectorAll('.qm-motion-ripple,.qm-motion-sheen').length,0,'Old ripple/sheen defer to the new owner.');
  summary.click();summary.click();await delay(35);assert.equal(doc.querySelectorAll('.qm-motion-exit').length,0,'Disclosure feedback creates no closing clone.');
  pointer(doc.querySelector('#unowned'),'pointerdown');assert.equal(doc.querySelectorAll('.qm-motion-ripple').length,1,'Unrelated controls retain previous feedback.');
  win.__qingmengMotion.dispose();

  details.open=true;pointer(target,'pointerover');await delay(50);media.matches=true;listeners.forEach(fn=>fn());
  assert.equal(api.getState().running,0);assert.equal(opened(summary),1,'Reduced motion settles at truthful open state.');
  details.open=false;await delay(55);assert.equal(opened(summary),0);media.matches=false;listeners.forEach(fn=>fn());
  details.open=true;await delay(50);Object.defineProperty(doc,'hidden',{value:true,configurable:true});doc.dispatchEvent(new win.Event('visibilitychange'));
  assert.equal(api.getState().running,0);assert.equal(opened(summary),1);assert.equal(hover(target),0);
  Object.defineProperty(doc,'hidden',{value:false,configurable:true});doc.dispatchEvent(new win.Event('visibilitychange'));
  doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.Event('qm-motion-preference-change'));
  details.open=false;await delay(55);assert.equal(opened(summary),0);assert.equal(api.getState().running,0);
  doc.documentElement.dataset.qmMotionMode='presentation';win.dispatchEvent(new win.Event('qm-motion-preference-change'));
  details.open=true;await delay(45);intersections[0].callback([{target:summary,isIntersecting:false}]);assert.equal(opened(summary),1);assert.equal(api.getState().running,0);
  const resultHost=target.closest('[class*="st-key-workspace_search_item_"]');pointer(target,'pointerover');await delay(45);
  intersections[0].callback([{target:resultHost,isIntersecting:false}]);assert.equal(hover(target),0);assert.equal(api.getState().running,0);
  const same=api;win.eval(read('feature_workflow.js'));assert.equal(win.QMFeatureWorkflow,same);assert.equal(doc.querySelectorAll('.qm-ui-expander-mark').length,1);
  const replacement=doc.createElement('section');replacement.setAttribute('data-testid','stExpander');replacement.innerHTML='<details open><summary><div><span><span data-testid="stIconMaterial">keyboard_arrow_down</span></span><div>新的章节</div></div></summary><div>原生内容</div></details>';
  details.parentElement.replaceWith(replacement);await delay(65);assert.equal(doc.querySelectorAll('.qm-ui-expander-mark').length,1);assert.equal(api.getState().disclosures,1);
  assert.equal(replacement.querySelector('[data-testid="stIconMaterial"]').dataset.qmUiChevron,'true','The default leading native chevron is identified too.');
  assert.equal(summary.querySelector('.qm-ui-expander-mark'),null);assert.equal(summary.dataset.qmUiDisclosure,undefined);assert.equal(summary.style.getPropertyValue('--qm-ui-open'),'');
  assert.equal(newChevron.dataset.qmUiChevron,undefined,'Unmount restores an originally absent native-icon marker.');
  replacement.remove();await delay(65);assert.equal(api.getState().disclosures,0,'Removing a native expander without replacement releases its observer and decoration.');
  assert.equal(replacement.querySelector('.qm-ui-expander-mark'),null);
  assert.equal(replacement.querySelector('[data-testid="stIconMaterial"]').dataset.qmUiChevron,undefined);
  doc.querySelector('main').appendChild(replacement);await delay(65);
  for(const node of chrome)assert.equal(node.style.transform,'','Every button retains its original hitbox.');
  api.dispose();assert.equal(listeners.size,0);assert.equal(doc.querySelectorAll('[data-qm-ui-button],[data-qm-ui-disclosure],[data-qm-ui-chevron="true"],.qm-ui-active-line,.qm-ui-expander-mark').length,0);
  assert.equal(header.style.getPropertyValue('--qm-ui-focus'),'');assert.equal(search.value,searchValue);assert.equal(field.value,'-123.45');assert.deepEqual(errors,[]);
  win.gsap.ticker.sleep();win.close();
  const fallback=new JSDOM(`<!doctype html><body>${markup}</body>`,{runScripts:'outside-only',pretendToBeVisual:true});
  fallback.window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});fallback.window.eval(read('feature_workflow.js'));await delay(45);
  const fallbackDoc=fallback.window.document,fallbackDetails=fallbackDoc.querySelector('#details');fallbackDetails.querySelector('summary').click();assert.equal(fallbackDetails.open,true);
  assert.equal(fallbackDoc.querySelectorAll('[data-qm-ui-button],[data-qm-ui-disclosure],.qm-ui-expander-mark').length,0,'Without GSAP the authored native fallback remains fully usable.');
  assert.equal(fallbackDoc.querySelector('#native-chevron').dataset.qmUiChevron,'authored','Without GSAP the original native arrow marker is untouched.');
  assert.equal(fallbackDoc.querySelector('#custom-icon').dataset.qmUiChevron,undefined);assert.equal(fallbackDoc.querySelector('#label-icon').dataset.qmUiChevron,undefined);
  fallback.window.QMFeatureWorkflow.dispose();fallback.window.close();
  console.log('interface chrome: confirmed-only evidence state, reversible decoration, native forms/downloads/disclosures, single owner, focus/value integrity, quiet/hidden/offscreen and disposal passed');
})().catch(error=>{win.QMFeatureWorkflow?.dispose();win.__qingmengMotion?.dispose();win.gsap?.ticker.sleep();win.close();console.error(error);process.exitCode=1;});
