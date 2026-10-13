'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom'),read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));vc.on('warn',e=>errors.push(String(e)));
const dom=new JSDOM('<!doctype html><html><body></body></html>',{runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
const win=dom.window,doc=win.document,frames=new Map(),mediaListeners=new Set(),observers=[],tweens=[];let nextFrame=0;
const media={matches:false,addEventListener:(_,fn)=>mediaListeners.add(fn),removeEventListener:(_,fn)=>mediaListeners.delete(fn)};win.matchMedia=()=>media;
win.IntersectionObserver=class{constructor(fn){this.fn=fn;this.nodes=new Set();observers.push(this);}observe(n){this.nodes.add(n);}unobserve(n){this.nodes.delete(n);}disconnect(){this.nodes.clear();}};
win.Element.prototype.getBoundingClientRect=()=>({left:0,top:20,right:560,bottom:230,width:560,height:210});
win.eval(read('vendor/gsap/gsap.min.js'));const realTo=win.gsap.to;win.gsap.to=function(...args){const tween=realTo.apply(this,args);tweens.push(tween);return tween;};
win.requestAnimationFrame=fn=>{frames.set(++nextFrame,fn);return nextFrame;};win.cancelAnimationFrame=id=>frames.delete(id);
async function flush(){for(let i=0;i<4;i++){await Promise.resolve();const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn(0));tweens.forEach(t=>t.pause());}}
function asset(key){const node=doc.createElement('div');node.className='st-key-guided_card_'+key;node.innerHTML='<div class="st-key-'+key+'"><button type="button"><strong>原生资产入口</strong><p>保留原动作</p></button></div>';doc.body.append(node);return node;}
(async()=>{
  // Head execution with no body must be bounded and capable of detecting the
  // two actual asset hosts when React mounts them later.
  doc.body.remove();win.eval(read('tool_entries.js'));await flush();assert.equal(frames.size,0);
  doc.documentElement.append(doc.createElement('body'));const draft=doc.createElement('input');draft.value='未提交的资产备注';doc.body.append(draft);draft.focus();
  let host=asset('asset_import_entry');const library=asset('asset_library_entry'),ignored=asset('asset_unrelated');await flush();
  const api=win.QMToolEntries;assert.equal(api.getState().entries,2);assert.equal(doc.querySelectorAll('[data-tool-injected]').length,2);assert.equal(ignored.querySelector('[data-tool-injected]'),null);
  const native=host.querySelector('button');let clicks=0;native.addEventListener('click',()=>clicks++);
  let art=host.querySelector('[data-tool-injected]');assert.equal(art.getAttribute('aria-hidden'),'true');assert.equal(art.inert,true);assert.equal(native.dataset.qmUiButton,'true');
  assert.equal(art.querySelectorAll('.tool-entry-plane').length,6);assert.equal(art.querySelector('button,input,a'),null);
  native.dispatchEvent(new win.MouseEvent('pointerover',{bubbles:true}));const entering=tweens.at(-1);entering.pause().progress(.55);const value=+art.style.getPropertyValue('--tool-hover');assert.ok(value>0&&value<1);
  native.dispatchEvent(new win.MouseEvent('pointerout',{bubbles:true}));const leaving=tweens.at(-1);leaving.pause().progress(.5);assert.equal(entering.parent,null);assert.ok(+art.style.getPropertyValue('--tool-hover')<value);
  assert.equal(host.style.transform,'');assert.equal(native.style.transform,'');assert.equal(native.style.opacity,'');assert.equal(draft.value,'未提交的资产备注');assert.equal(doc.activeElement,draft);assert.equal(clicks,0);
  native.click();assert.equal(clicks,1);native.focus();tweens.at(-1).pause().progress(1);assert.equal(+art.style.getPropertyValue('--tool-hover'),1);
  // Re-running bootstrap and scanning the injected sibling is idempotent.
  win.eval(read('tool_entries.js'));api.refresh();await flush();assert.equal(win.QMToolEntries,api);assert.equal(doc.querySelectorAll('[data-tool-injected]').length,2);
  const oldArt=art;host.remove();await flush();assert.equal(api.getState().entries,1);assert.equal(oldArt.isConnected,false);assert.equal(native.hasAttribute('data-qm-ui-button'),false);
  host=asset('asset_import_entry');await flush();art=host.querySelector('[data-tool-injected]');assert.equal(+art.style.getPropertyValue('--tool-enter'),1,'Native remount keeps completed entry.');
  media.matches=true;for(const fn of mediaListeners)fn();assert.equal(api.getState().running,0);assert.equal(+art.style.getPropertyValue('--tool-hover'),0);
  media.matches=false;for(const fn of mediaListeners)fn();for(const io of observers)if(io.nodes.has(host))io.fn([{target:host,isIntersecting:false}]);assert.equal(+art.style.getPropertyValue('--tool-hover'),0);
  api.dispose();await flush();assert.equal(doc.querySelectorAll('[data-tool-injected]').length,0);assert.equal(host.hasAttribute('data-tool-asset'),false);assert.equal(library.hasAttribute('data-tool-asset'),false);assert.equal(mediaListeners.size,0);assert.equal(frames.size,0);assert.ok(tweens.every(t=>t.parent===null||t.progress()===1),'Every unfinished owned tween is removed; manually completed paused test tweens cannot run.');assert.deepEqual(errors,[]);
  console.log('entry planes v22: real GSAP asset hover/focus/reverse, native actions/drafts, allowlist, body-late injection, same-key remount, reduced/offscreen and removal cleanup passed');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{win.QMToolEntries?.dispose();win.gsap.ticker.sleep();win.close();});
