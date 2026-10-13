/* An explicit guide action may focus one native field; it never clicks or submits. */
(function(root){
  'use strict';
  function install(win,doc){
    const version='20261011.23';
    if(win.QMWorkspaceGuideFocus&&win.QMWorkspaceGuideFocus.version===version){win.QMWorkspaceGuideFocus.scan();return win.QMWorkspaceGuideFocus;}
    if(win.QMWorkspaceGuideFocus)win.QMWorkspaceGuideFocus.dispose();
    const done=new Set();let observer=null,timer=null,frame=0,active=null,disposed=false;
    const selectors={question:'.st-key-qa_composer input[aria-label="自然语言问题"]',selection:'.st-key-qa_scope [role="combobox"]'};
    function stop(){if(observer)observer.disconnect();observer=null;if(timer)win.clearTimeout(timer);timer=null;if(frame)win.cancelAnimationFrame(frame);frame=0;}
    function tryFocus(){
      frame=0;if(disposed||!active)return;
      let target=doc.querySelector(selectors[active.target]);
      if(!target||!target.isConnected||target.disabled)return;
      let rect=target.getBoundingClientRect();
      if((rect.width<=0||rect.height<=0)&&active.target==='selection'){
        target=doc.querySelector('.st-key-qa_scope_shell summary');
        if(!target||!target.isConnected)return;rect=target.getBoundingClientRect();
      }
      if(rect.width<=0||rect.height<=0)return;
      done.add(active.id);while(done.size>32)done.delete(done.values().next().value);
      stop();target.scrollIntoView({behavior:'instant',block:'center',inline:'nearest'});
      target.focus({preventScroll:true});active=null;
    }
    function scan(){
      const marker=doc.querySelector('[data-qm-guide-focus][data-qm-guide-request]');
      if(!marker||disposed)return;
      const id=marker.getAttribute('data-qm-guide-request'),target=marker.getAttribute('data-qm-guide-focus');
      if(!id||!selectors[target]||done.has(id)||active&&active.id===id)return;
      stop();active={id,target};
      observer=new win.MutationObserver(()=>{if(!frame)frame=win.requestAnimationFrame(tryFocus);});
      observer.observe(doc.body,{childList:true,subtree:true});
      timer=win.setTimeout(()=>{done.add(id);stop();active=null;},5000);
      frame=win.requestAnimationFrame(tryFocus);
    }
    function dispose(){disposed=true;stop();active=null;win.removeEventListener('pagehide',dispose);}
    const api={version,scan,dispose};win.QMWorkspaceGuideFocus=api;win.addEventListener('pagehide',dispose);scan();return api;
  }
  if(typeof module==='object'&&module.exports)module.exports={install};
  else install(root,root.document);
})(typeof window!=='undefined'?window:globalThis);
