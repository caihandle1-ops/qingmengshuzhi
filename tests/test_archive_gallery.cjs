'use strict';
// Real bundled GSAP against controlled geometry. This checks behaviour, not pixels.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error.message));
const dom=new JSDOM('<!doctype html><html><head></head><body><main><div data-studio-scene="assets-library"></div><input id="business" value="0 / -123.45 / 缺失"><div id="outlet"></div></main></body></html>',
  {url:'http://127.0.0.1:8504/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc});
const win=dom.window,doc=win.document,observers=[];
const reduced={matches:false,addEventListener(){},removeEventListener(){}};win.matchMedia=()=>reduced;
win.IntersectionObserver=class{constructor(fn){this.fn=fn;this.targets=new Set();observers.push(this);}observe(node){this.targets.add(node);}unobserve(node){this.targets.delete(node);}disconnect(){this.targets.clear();}};
Object.defineProperty(win,'innerWidth',{value:1600,configurable:true});Object.defineProperty(win,'innerHeight',{value:1000,configurable:true});
win.Element.prototype.getBoundingClientRect=function(){
  const card=this.closest?.('[data-archive-record]'),id=Number(card?.getAttribute('data-archive-record')||0);
  const directory=doc.querySelector('[data-archive-mode]')?.getAttribute('data-archive-mode')==='directory';
  const box=this.matches?.('[data-archive-desk-face]')?{left:1040,top:340,width:120,height:160}:
    card?(directory?{left:60,top:110+(id-1)*125,width:72,height:92}:{left:60+(id-1)*225,top:130,width:180,height:255}):{left:40,top:80,width:1300,height:650};
  return {...box,x:box.left,y:box.top,right:box.left+box.width,bottom:box.top+box.height};
};
win.eval(fs.readFileSync(path.join(__dirname,'../app/vendor/gsap/gsap.min.js'),'utf8'));
const source=fs.readFileSync(path.join(__dirname,'../app/archive_gallery.js'),'utf8');
const png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6X8AAAAASUVORK5CYII=';
const face=id=>`<div class="archive-original-page"><img src="${png}" alt=""></div><div class="archive-cover-label">原件首页 · 实际文件${id}.pdf</div>`;
function mount(commit,selected='1',open='',mode='shelf'){
  doc.getElementById('outlet').innerHTML=`<section class="st-key-archive_gallery"><div class="st-key-archive_gallery_shelf">${[1,2,3,4].map(id=>
    `<div class="st-key-archive_document_card_${id}"><div data-archive-record="${id}"><div class="archive-arrival"><div class="archive-parallax"><div class="archive-volume" style="transform:rotateY(${String(id)===open?0:-12}deg)"><div class="archive-front" data-archive-face>${face(id)}</div></div></div></div></div><button>查看实际文件${id}</button></div>`).join('')}</div>
    <div data-archive-desk="${selected}"><div data-archive-desk-face>${face(selected)}</div></div>
    <span hidden data-archive-mode="${mode}" data-archive-commit="${commit}" data-archive-selected="${selected}" data-archive-open="${open}"></span></section>`;
}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const state=()=>win.QMArchiveGallery.getState();
function finish(){for(const target of doc.querySelectorAll('.archive-arrival,.archive-volume,.qm-archive-flight'))for(const tween of win.gsap.getTweensOf(target))tween.progress(1);}
async function run(){
  const business=doc.getElementById('business');business.focus();mount('a');win.eval(source);await delay(65);
  assert.equal(state().records,4);assert.ok(state().active>0,'The real GSAP shelf entrance is running.');
  const oldEntrances=[...doc.querySelectorAll('.archive-arrival')];
  mount('a');await delay(45);
  assert.equal(win.gsap.getTweensOf(oldEntrances).length,0,'Detached entrance nodes are released on an equal-commit remount.');
  finish();assert.equal(state().flights,0);assert.equal(state().phase,'closed');
  doc.querySelector('.st-key-archive_document_card_2 button').click();await delay(30);
  assert.equal(state().flights,0,'Clicking does not pretend native selection already completed.');
  mount('b','2','2');await delay(65);
  assert.equal(state().phase,'extracting');assert.equal(state().flights,1);
  const flight=doc.querySelector('.qm-archive-flight');
  assert.ok(flight.textContent.includes('实际文件2.pdf'),'Extraction carries this actual selected file face, not blank paper.');
  assert.equal(flight.querySelector('img').getAttribute('src'),png);
  assert.equal(flight.getAttribute('aria-hidden'),'true');assert.equal(flight.inert,true);
  assert.equal(flight.querySelector('button,input,iframe'),null);
  const transform=flight.style.transform;await delay(90);
  assert.notEqual(flight.style.transform,transform,'The real GSAP engine moves the actual document cover.');
  assert.equal(business.value,'0 / -123.45 / 缺失');assert.equal(doc.activeElement,business);
  assert.equal(win.gsap.getTweensOf(business).length,0);
  finish();assert.equal(state().phase,'open');assert.equal(state().flights,0);
  const singleton=win.QMArchiveGallery;mount('b','2','2');win.eval(source);await delay(50);
  assert.equal(win.QMArchiveGallery,singleton);assert.equal(state().flights,0);assert.equal(state().active,0,'Equal native rerenders do not replay extraction.');
  mount('c','2','');await delay(55);
  assert.equal(state().phase,'returning');assert.equal(state().flights,1);
  assert.ok(doc.querySelector('.qm-archive-flight').textContent.includes('实际文件2.pdf'));
  finish();assert.equal(state().phase,'closed');assert.equal(state().flights,0);

  doc.querySelector('.st-key-archive_document_card_2 button').click();
  mount('c-mode','2','','directory');await delay(60);
  assert.equal(state().flights,0,'Changing the browsing layout never pretends a source opened.');
  assert.ok(state().active>0,'The same document art moves continuously between shelf and catalogue positions.');
  assert.ok(doc.querySelector('.archive-arrival').style.transform);
  assert.equal(doc.querySelector('.st-key-archive_document_card_2 button').style.transform,'','The native target remains stationary during catalogue reflow.');
  finish();mount('c-mode','2','','directory');await delay(45);
  assert.equal(state().active,0,'Equal catalogue commits do not replay the rearrangement.');
  mount('c-select','1','','directory');await delay(60);
  assert.equal(state().flights,1,'Choosing another document carries its cover to the desk without claiming an open source.');
  assert.ok(doc.querySelector('.qm-archive-flight').textContent.includes('实际文件1.pdf'));
  finish();assert.equal(state().phase,'closed');

  mount('d','3','3');await delay(50);assert.equal(state().flights,1);
  Object.defineProperty(doc,'hidden',{configurable:true,value:true});doc.dispatchEvent(new win.Event('visibilitychange'));
  assert.equal(state().flights,0);assert.equal(state().active,0,'Backgrounding settles all document travel immediately.');
  Object.defineProperty(doc,'hidden',{configurable:true,value:false});doc.dispatchEvent(new win.Event('visibilitychange'));await delay(45);
  assert.equal(state().flights,0,'Returning cannot replay a consumed selection.');
  doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.Event('qm-motion-preference-change'));
  mount('e','4','4');await delay(50);assert.equal(state().flights,0);assert.equal(state().active,0);assert.equal(state().phase,'open');
  delete doc.documentElement.dataset.qmMotionMode;win.dispatchEvent(new win.Event('qm-motion-preference-change'));await delay(30);
  assert.equal(state().flights,0);
  const card=doc.querySelector('.st-key-archive_document_card_4');
  card.dispatchEvent(new win.MouseEvent('pointermove',{clientX:890,clientY:140,bubbles:true}));await delay(60);
  assert.ok(card.querySelector('.archive-parallax').style.transform,'Pointer depth only targets the decorative wrapper.');
  assert.equal(win.gsap.getTweensOf(card.querySelector('button')).length,0);
  doc.querySelector('[data-studio-scene]').setAttribute('data-studio-scene','qa');doc.getElementById('outlet').replaceChildren();await delay(55);
  assert.equal(state().records,0);assert.equal(state().flights,0);assert.equal(state().active,0);
  assert.equal(doc.querySelector('.qm-archive-flight'),null,'Leaving the library removes every copied file face.');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,real_gsap:true,actual_file_face_extraction_and_return:true,
    native_commit_authority:true,same_commit_no_replay:true,hidden_quiet_cleanup:true,native_input_untouched:true,catalogue_shelf_reflow:true,closed_selection_cover_continuity:true}));
}
run().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{win.QMArchiveGallery?.dispose();win.gsap?.ticker.sleep();dom.window.close();});
