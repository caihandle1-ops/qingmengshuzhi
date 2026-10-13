/* Spatial links use the rendered, deformed paper triangles; no inferred business data. */
(function(global){
  'use strict';
  const ACTIONS=['annual_reports','annual_data','answer_evidence'];
  const LABELS={annual_reports:'年度报告',annual_data:'结构化数据',answer_evidence:'答案与依据',enter_workspace:'进入研究空间'};
  const transform=(m,x,y,z)=>[m[0]*x+m[4]*y+m[8]*z+m[12],m[1]*x+m[5]*y+m[9]*z+m[13],m[2]*x+m[6]*y+m[10]*z+m[14],m[3]*x+m[7]*y+m[11]*z+m[15]];
  function project(surfaces,vp,rect){
    if(!vp||!rect||!rect.width||!rect.height)return [];
    return surfaces.map(surface=>{
      const points=[];let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;
      for(let i=0;i<surface.vertices.length;i+=9){
        const a=transform(surface.matrix,surface.vertices[i],surface.vertices[i+1],surface.vertices[i+2]);
        const p=transform(vp,a[0],a[1],a[2]);
        if(p[3]<=0){points.push(null);continue;}
        const point=[rect.left+(p[0]/p[3]+1)*rect.width/2,rect.top+(1-p[1]/p[3])*rect.height/2,p[2]/p[3]];
        points.push(point);left=Math.min(left,point[0]);right=Math.max(right,point[0]);top=Math.min(top,point[1]);bottom=Math.max(bottom,point[1]);
      }
      left=Math.max(rect.left,left);right=Math.min(rect.left+rect.width,right);
      top=Math.max(rect.top,top);bottom=Math.min(rect.top+rect.height,bottom);
      return {action:surface.action,points,indices:surface.indices,rect:{left,top,width:Math.max(0,right-left),height:Math.max(0,bottom-top)}};
    });
  }
  function hit(projected,x,y){
    let best=null,depth=Infinity;
    for(const surface of projected){
      const r=surface.rect;if(x<r.left||x>r.left+r.width||y<r.top||y>r.top+r.height)continue;
      for(let i=0;i<surface.indices.length;i+=3){
        const a=surface.points[surface.indices[i]],b=surface.points[surface.indices[i+1]],c=surface.points[surface.indices[i+2]];
        if(!a||!b||!c)continue;
        const denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
        if(Math.abs(denominator)<1e-8)continue;
        const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator;
        const v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator,w=1-u-v;
        if(u<0||v<0||w<0)continue;
        const z=u*a[2]+v*b[2]+w*c[2];
        if(z>=-1&&z<=1&&z<depth){depth=z;best=surface;}
      }
    }
    return best;
  }
  function createNavigation(env){
    const doc=env.document,links=ACTIONS.map(action=>doc.getElementById('hero-link-'+action));
    const label=doc.getElementById('hero-object-label'),contextLabel=doc.getElementById('hero-context-label');
    let context={token:''},pending=null,completePending=null,hovered=null,focused=null,disposed=false,counter=0,landing=false;
    const enter=doc.getElementById('landing-enter');
    let surfaces=[],vp=null,rect=null,projected=null;
    const sent=new Set();
    const geometry=()=>projected||(projected=project(surfaces,vp,rect));
    function description(action){
      if(action==='enter_workspace')return '打开财报研究工作区';
      const present=action==='annual_reports'?context.has_reports:action==='annual_data'?context.has_data:context.has_answer;
      return present?{annual_reports:'查阅已接入的年度报告',annual_data:'查看企业年度指标',answer_evidence:'打开当前答案与来源'}[action]
        :{annual_reports:'前往资料库接入报告',annual_data:'前往数据资产接入指标',answer_evidence:'从一个财务问题开始'}[action];
    }
    function refresh(){
      const active=pending?.action||focused||hovered;
      env.shell.dataset.navigationReady=context.token?'true':'false';
      env.shell.dataset.navigationActive=active||'';
      links.forEach((link,index)=>{
        if(!link)return;const action=ACTIONS[index];
        link.setAttribute('aria-disabled',context.token?'false':'true');link.tabIndex=context.token?0:-1;
        link.setAttribute('aria-label',LABELS[action]+'，'+description(action));link.dataset.active=String(active===action);
      });
      if(enter){enter.setAttribute('aria-disabled',landing&&context.token?'false':'true');enter.tabIndex=landing&&context.token?0:-1;}
      if(contextLabel)contextLabel.textContent=[context.company,context.year&&String(context.year).match(/^\d{4}$/)?context.year+'年度':context.year].filter(Boolean).join(' · ')||'选择物件，进入研究';
      if(label){label.hidden=!active||!context.token;label.textContent=active?LABELS[active]+'  ↗  '+description(active):'';}
      env.onHover(active);
    }
    function setContext(value){
      value=value&&typeof value==='object'?value:{};
      const token=typeof value.token==='string'&&/^[A-Za-z0-9_.:-]{1,96}$/.test(value.token)?value.token:'';
      if(token!==context.token){pending=null;completePending=null;hovered=focused=null;env.cancel();}
      context={token,company:typeof value.company==='string'?value.company.slice(0,100):'',year:typeof value.year==='string'?value.year.slice(0,24):'',
        has_reports:value.has_reports===true,has_data:value.has_data===true,has_answer:value.has_answer===true};
      refresh();
    }
    function activate(action,sourceRect){
      if(disposed||pending||!context.token||!(ACTIONS.includes(action)||(landing&&action==='enter_workspace')))return false;
      const nonce=global.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+(++counter);
      const event={action,nonce,context_token:context.token};pending=event;refresh();
      const target=geometry().filter(surface=>surface.action===action&&surface.rect.width>0&&surface.rect.height>0)
        .sort((a,b)=>b.rect.width*b.rect.height-a.rect.width*a.rect.height)[0];
      env.intent(event,target?.rect||sourceRect,LABELS[action]);
      const current=()=>!disposed&&pending===event&&context.token===event.context_token;
      if(!current()||sent.has(nonce))return false;
      // The validated click owns navigation. The 430/620ms physical exit is
      // decorative and can continue while Streamlit prepares the next view.
      // Keep the lock until context replacement or disposal, including after
      // visual completion, so reruns and repeated clicks cannot replay it.
      sent.add(nonce);if(sent.size>32)sent.delete(sent.values().next().value);
      env.emit(event);
      if(!current())return true;
      const finish=()=>{if(current())completePending=null;};
      completePending=finish;env.begin(action,finish);return true;
    }
    links.forEach((link,index)=>{
      if(!link)return;const action=ACTIONS[index];
      env.listen(link,'focus',()=>{focused=action;refresh();});
      env.listen(link,'blur',()=>{focused=null;refresh();});
      env.listen(link,'click',event=>{event.preventDefault();if(event.button&&event.button!==0)return;activate(action,link.getBoundingClientRect());});
      env.listen(link,'keydown',event=>{if(event.key===' '){event.preventDefault();activate(action,link.getBoundingClientRect());}});
    });
    if(enter)env.listen(enter,'click',event=>{event.preventDefault();activate('enter_workspace',enter.getBoundingClientRect());});
    refresh();
    return {setContext,
      setLanding(value){if(landing===!!value)return;landing=!!value;pending=null;completePending=null;env.cancel();refresh();},
      get ready(){return !!context.token;},
      setScene(nextSurfaces,nextVP,nextRect){surfaces=nextSurfaces;vp=nextVP;rect=nextRect;projected=null;},
      hoverAt(x,y){if(disposed||pending)return;const found=context.token?hit(geometry(),x,y):null;const action=found?.action||null;if(hovered!==action){hovered=action;refresh();}},
      clearHover(){if(hovered){hovered=null;refresh();}},
      selectAt(x,y){const found=context.token?hit(geometry(),x,y):null;return found?activate(found.action,found.rect):false;},
      settlePending(){completePending?.();env.cancel();},
      getState:()=>({ready:!!context.token,hovered,focused,pending:pending?{...pending}:null,disposed}),
      getTargets:()=>geometry().map(surface=>({action:surface.action,rect:{...surface.rect}})),
      hitTest:(x,y)=>hit(geometry(),x,y)?.action||null,
      dispose(){disposed=true;pending=null;completePending=null;surfaces=[];projected=null;env.cancel();}
    };
  }
  global.QMHeroNavigation={createNavigation,project,hit};
})(typeof window!=='undefined'?window:globalThis);
