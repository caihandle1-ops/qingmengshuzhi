/* Local native WebGL sculpture. No network, business events, or financial inputs. */
(function () {
  'use strict';
  const canvas=document.getElementById('sculpture');
  const shell=document.getElementById('hero');
  const stageElement=document.getElementById('sculpture-stage');
  const toggle=document.getElementById('assembly-toggle');
  const buttons=Array.from(document.querySelectorAll('[data-phase]'));
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  const coarse=window.matchMedia('(pointer: coarse)');
  const forced=window.matchMedia('(forced-colors: active)');
  const cleanup=[];
  let graphics=null, runtime=null, disposed=false;
  function listen(target,type,fn,options){target.addEventListener(type,fn,options);cleanup.push(()=>target.removeEventListener(type,fn,options));}
  function send(type,extra){window.parent.postMessage(Object.assign({isStreamlitMessage:true,type},extra||{}),'*');}
  const identity=()=>new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
  function mul(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
  function translate(x,y,z){const m=identity();m[12]=x;m[13]=y;m[14]=z;return m;}
  function scale(x,y,z){const m=identity();m[0]=x;m[5]=y;m[10]=z;return m;}
  function rotateX(a){const m=identity(),c=Math.cos(a),s=Math.sin(a);m[5]=c;m[6]=s;m[9]=-s;m[10]=c;return m;}
  function rotateY(a){const m=identity(),c=Math.cos(a),s=Math.sin(a);m[0]=c;m[2]=-s;m[8]=s;m[10]=c;return m;}
  function rotateZ(a){const m=identity(),c=Math.cos(a),s=Math.sin(a);m[0]=c;m[1]=s;m[4]=-s;m[5]=c;return m;}
  function model(p){return mul(translate(p[0],p[1],p[2]),mul(rotateZ(p[5]),mul(rotateY(p[4]),mul(rotateX(p[3]),scale(p[6],p[7],p[8])))));}
  function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2),m=new Float32Array(16);m[0]=f/aspect;m[5]=f;m[10]=(far+near)/(near-far);m[11]=-1;m[14]=2*far*near/(near-far);return m;}
  const mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
  const COLORS={blue:[.13,.30,.96],paper:[.91,.94,.97],silver:[.60,.71,.87],orange:[1,.56,.28],lime:[.86,.96,.46],ink:[.09,.15,.24]};
  function cubeVertices(){
    const faces=[
      [[-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5],[0,0,1],1],
      [[.5,-.5,-.5],[-.5,-.5,-.5],[-.5,.5,-.5],[.5,.5,-.5],[0,0,-1],0],
      [[.5,-.5,.5],[.5,-.5,-.5],[.5,.5,-.5],[.5,.5,.5],[1,0,0],0],
      [[-.5,-.5,-.5],[-.5,-.5,.5],[-.5,.5,.5],[-.5,.5,-.5],[-1,0,0],0],
      [[-.5,.5,.5],[.5,.5,.5],[.5,.5,-.5],[-.5,.5,-.5],[0,1,0],0],
      [[-.5,-.5,-.5],[.5,-.5,-.5],[.5,-.5,.5],[-.5,-.5,.5],[0,-1,0],0],
    ],out=[],uv=[[0,0],[1,0],[1,1],[0,1]];
    faces.forEach(face=>[0,1,2,0,2,3].forEach(i=>out.push(...face[i],...face[4],...uv[i],face[5])));
    return new Float32Array(out);
  }
  function torusVertices(radius,tube,start=0,arc=Math.PI*2){
    const out=[],segments=100,sides=6;
    function vertex(i,j){const a=start+arc*i/segments,b=Math.PI*2*j/sides,c=Math.cos(a),s=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b);return [c*(radius+tube*cb),s*(radius+tube*cb),tube*sb,c*cb,s*cb,sb,0,0,0];}
    for(let i=0;i<segments;i++)for(let j=0;j<sides;j++)out.push(...vertex(i,j),...vertex(i+1,j),...vertex(i+1,j+1),...vertex(i,j),...vertex(i+1,j+1),...vertex(i,j+1));
    return new Float32Array(out);
  }
  function makeTexture(kind){
    const sheet=document.createElement('canvas');sheet.width=512;sheet.height=720;const c=sheet.getContext('2d');
    if(!c)throw new Error('Texture canvas unavailable');
    const blue=kind==='cover',lime=kind==='index',answer=kind==='answer';
    c.fillStyle=blue?'#2454f4':lime?'#e3f398':answer?'#f4a670':'#edf0f4';c.fillRect(0,0,512,720);
    // Fixed, low-contrast fibres: the material is visible without moving the type.
    let seed=271828;for(let i=0;i<5200;i++){seed=(seed*1664525+1013904223)>>>0;const x=seed%512;seed=(seed*1664525+1013904223)>>>0;const y=seed%720;c.fillStyle=i%2?'#ffffff0b':'#07172b08';c.fillRect(x,y,1+(i%3),1);}
    const spine=c.createLinearGradient(0,0,40,0);spine.addColorStop(0,'#07172b42');spine.addColorStop(.36,'#07172b0c');spine.addColorStop(.46,'#ffffff24');spine.addColorStop(1,'#ffffff00');c.fillStyle=spine;c.fillRect(0,0,40,720);
    c.strokeStyle=blue?'#b6c9ff66':'#ffffff99';c.lineWidth=1.5;c.strokeRect(1.5,1.5,509,717);
    c.fillStyle=blue?'#edf2ff':'#14233d';c.font='500 20px Arial';c.fillText(blue?'ANNUAL REPORT':lime?'SOURCE INDEX':answer?'RESEARCH EVIDENCE':'FINANCIAL RECORDS',42,61);
    c.fillStyle=blue?'#e8f59b':'#17273e';c.font='600 58px "Microsoft YaHei",sans-serif';
    c.fillText(blue?'年度':lime?'原始':answer?'答案':'结构化',39,180);c.fillText(blue?'报告':lime?'依据':answer?'与依据':'数据',39,248);
    c.strokeStyle=blue?'#8ba8ff':'#152b4555';c.lineWidth=2;c.beginPath();c.moveTo(42,298);c.lineTo(469,298);c.stroke();
    if(blue){
      c.strokeStyle='#e7f59a';c.lineWidth=8;c.beginPath();c.moveTo(45,522);c.lineTo(139,453);c.lineTo(239,475);c.lineTo(332,378);c.lineTo(465,412);c.stroke();
      c.fillStyle='#e7f59a';[[45,522],[139,453],[239,475],[332,378],[465,412]].forEach(p=>{c.beginPath();c.arc(p[0],p[1],8,0,Math.PI*2);c.fill();});
      c.font='22px "Microsoft YaHei",sans-serif';c.fillStyle='#e7edff';c.fillText('从记录，走向有据的答案。',42,628);
    }else if(answer||lime){
      c.font='23px "Microsoft YaHei",sans-serif';c.fillStyle='#20314a';['企业 · 年度 · 指标','原始记录 · 来源定位','口径与证据相互对应'].forEach((text,i)=>{c.fillText(text,42,375+i*67);c.fillStyle='#17273e33';c.fillRect(42,394+i*67,425,2);c.fillStyle='#20314a';});
      c.font='18px "Microsoft YaHei",sans-serif';c.fillText('产品研究路径示意',42,648);
    }else{
      c.strokeStyle='#7890af88';c.lineWidth=1.5;for(let row=0;row<6;row++){c.beginPath();c.moveTo(42,350+row*41);c.lineTo(470,350+row*41);c.stroke();}for(let col=0;col<4;col++){c.beginPath();c.moveTo(42+col*143,350);c.lineTo(42+col*143,555);c.stroke();}
      c.fillStyle='#2857e9';[54,100,76,139].forEach((height,i)=>c.fillRect(64+i*99,687-height,43,height));
    }
    return sheet;
  }
  function createGraphics(){
    const gl=canvas.getContext('webgl',{alpha:true,antialias:true,depth:true,premultipliedAlpha:false,powerPreference:'low-power'});
    if(!gl)throw new Error('WebGL unavailable');
    const allocated={buffers:[],textures:[],shaders:[],programs:[]};
    function shader(type,source){const s=gl.createShader(type);allocated.shaders.push(s);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('Shader unavailable');return s;}
    const vs=shader(gl.VERTEX_SHADER,`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUV;attribute float aFront;uniform mat4 uModel;uniform mat4 uVP;varying vec3 vNormal;varying vec3 vPosition;varying vec2 vUV;varying float vFront;void main(){vec4 world=uModel*vec4(aPosition,1.0);vPosition=world.xyz;vNormal=normalize(mat3(uModel)*aNormal);vUV=aUV;vFront=aFront;gl_Position=uVP*world;}`);
    const fs=shader(gl.FRAGMENT_SHADER,`precision mediump float;
uniform vec3 uColor;uniform sampler2D uTexture;uniform float uHasTexture;uniform float uRoughness;uniform vec3 uEye;
varying vec3 vNormal;varying vec3 vPosition;varying vec2 vUV;varying float vFront;
void main(){
  vec3 base=uColor;bool face=uHasTexture>0.5&&vFront>0.5;if(face)base=texture2D(uTexture,vUV).rgb;
  vec3 n=normalize(vNormal),view=normalize(uEye-vPosition);
  vec3 key=normalize(vec3(-3.8,5.2,6.0)-vPosition),fill=normalize(vec3(4.5,1.4,2.0)-vPosition);
  float diffuse=max(dot(n,key),0.0),bounce=max(dot(n,fill),0.0);
  float gloss=pow(max(dot(n,normalize(key+view)),0.0),mix(100.0,12.0,uRoughness));
  float softbox=pow(max(dot(n,normalize(fill+view)),0.0),18.0);
  float fresnel=pow(1.0-max(dot(n,view),0.0),3.0);
  vec3 color=base*(0.48+0.43*diffuse)+base*vec3(0.69,0.80,1.0)*bounce*0.18;
  color+=vec3(1.0,0.90,0.75)*gloss*(1.0-uRoughness)*0.36;
  color+=vec3(0.68,0.82,1.0)*(softbox*0.09+fresnel*0.08);
  if(face){float edge=min(min(vUV.x,1.0-vUV.x),min(vUV.y,1.0-vUV.y));color+=vec3(0.62,0.75,0.98)*(1.0-smoothstep(0.0,0.006,edge))*0.14;}
  gl_FragColor=vec4(color,1.0);
}`);
    const program=gl.createProgram();allocated.programs.push(program);gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Program unavailable');gl.useProgram(program);
    const attr={};['Position','Normal','UV','Front'].forEach(name=>attr[name]=gl.getAttribLocation(program,'a'+name));
    const uni={};['Model','VP','Color','Texture','HasTexture','Eye','Roughness'].forEach(name=>uni[name]=gl.getUniformLocation(program,'u'+name));
    function buffer(data){const value=gl.createBuffer();allocated.buffers.push(value);gl.bindBuffer(gl.ARRAY_BUFFER,value);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);return {value,count:data.length/9};}
    const cube=buffer(cubeVertices()),ring=buffer(torusVertices(2.15,.013)),ribbon=buffer(torusVertices(2.20,.038,-.25,Math.PI*.82));
    const textures={};['cover','paper','answer','index'].forEach(kind=>{const texture=gl.createTexture();allocated.textures.push(texture);gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,makeTexture(kind));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);textures[kind]=texture;});
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);gl.clearColor(0,0,0,0);
    function mesh(geometry,matrix,color,texture){
      gl.bindBuffer(gl.ARRAY_BUFFER,geometry.value);const stride=9*4;
      [['Position',3,0],['Normal',3,12],['UV',2,24],['Front',1,32]].forEach(([name,size,offset])=>{gl.enableVertexAttribArray(attr[name]);gl.vertexAttribPointer(attr[name],size,gl.FLOAT,false,stride,offset);});
      gl.uniformMatrix4fv(uni.Model,false,matrix);gl.uniform3fv(uni.Color,color);gl.uniform1f(uni.HasTexture,texture?1:0);gl.uniform1f(uni.Roughness,texture===textures.cover?.30:texture?.76:.24);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture||textures.paper);gl.uniform1i(uni.Texture,0);gl.drawArrays(gl.TRIANGLES,0,geometry.count);
    }
    function draw(state){
      const rect=canvas.getBoundingClientRect(),ratio=Math.min(window.devicePixelRatio||1,2),width=Math.max(1,Math.round(rect.width*ratio)),height=Math.max(1,Math.round(rect.height*ratio));
      if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
      gl.viewport(0,0,width,height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
      const aspect=width/height,projection=perspective(.62,aspect,.1,60),distance=aspect<1?8.1:7.0;
      const px=state.pointer[0],py=state.pointer[1],idle=state.reduced?0:Math.sin(state.time*.43)*.035;
      const view=mul(translate(0,-.05,-distance),mul(rotateX(.08+py*.15),rotateY(-px*.29+idle)));
      gl.uniformMatrix4fv(uni.VP,false,mul(projection,view));gl.uniform3fv(uni.Eye,[0,0,distance]);
      const blend=state.stage<1?state.stage:state.stage-1,first=state.stage<1?0:1,second=first+1;
      function pose(poses,closed){const p=mix(poses[first],poses[second],blend),q=mix(closed,p,state.open);q[1]+=state.reduced?0:Math.sin(state.time*.62+q[0])*.035;return model(q);}
      // Every dimension and line is an illustrative object, never a financial value.
      for(let i=0;i<5;i++){
        const closed=[-.15+i*.026,.04+i*.009,-.08+i*.045,-.09,-.29,-.14,1.60,2.28,.028];
        const poses=[
          [-.27-i*.20,.08+i*.035,-.21-i*.11,-.1,-.35,-.18-i*.052,1.60,2.28,.028],
          [-.68+i*.32,.13+(i%2)*.09,-.53+i*.31,-.20+i*.04,-.47+i*.11,-.40+i*.15,1.58,2.28,.028],
          [-1.04-i*.11,.10+i*.04,-.17-i*.09,-.05,-.25,-.15-i*.036,1.42,2.11,.028],
        ];
        mesh(cube,pose(poses,closed),i%2?COLORS.paper:COLORS.silver,i===4?textures.paper:null);
      }
      mesh(cube,pose([
        [.17,.01,.51,-.07,-.32,-.16,1.65,2.32,.072],
        [-.98,.03,.61,-.16,-.45,-.30,1.65,2.32,.072],
        [-1.05,.04,.36,-.1,-.32,-.16,1.53,2.20,.072],
      ],[-.13,.01,.29,-.09,-.29,-.14,1.65,2.32,.072]),COLORS.blue,textures.cover);
      mesh(cube,pose([
        [1.27,-.43,-.14,.10,.28,.19,.74,1.10,.042],
        [1.14,-.24,.38,.10,.22,.18,.93,1.38,.042],
        [1.00,-.10,.76,.05,-.08,.13,1.55,2.08,.065],
      ],[.01,.01,-.18,-.09,-.29,-.14,1.48,2.18,.04]),COLORS.orange,textures.answer);
      mesh(cube,pose([
        [.80,.97,-.22,-.18,.38,.26,.64,.91,.035],
        [.79,1.08,-.03,-.14,.23,.15,.82,1.12,.035],
        [.74,1.26,-.37,-.18,.10,-.02,.78,1.02,.035],
      ],[.04,.02,-.24,-.09,-.29,-.14,1.40,2.08,.035]),COLORS.lime,textures.index);
      const orbitOpen=.72+.28*state.open;
      const orbit=mul(translate(0,-.02,-.2),mul(rotateZ(-.34),mul(rotateX(.96+idle),scale(orbitOpen,orbitOpen,orbitOpen))));
      mesh(ring,orbit,[.29,.41,.59]);
      mesh(ribbon,mul(orbit,rotateZ(state.reduced?.4:state.time*.23)),COLORS.lime);
      mesh(ring,mul(translate(.03,.12,-.24),mul(rotateZ(.27),mul(rotateX(1.10),scale(orbitOpen*.91,orbitOpen*.91,orbitOpen*.91)))),[.35,.41,.54]);
      // Four solid data bars re-form below the papers as the structure opens.
      [0,1,2,3].forEach(i=>{
        const h=[.35,.59,.46,.82][i],x=-.34+i*.25;
        mesh(cube,pose([
          [x,-1.60+h*.5,.25,0,-.18,0,.14,h,.16],
          [x+.34,-1.52+h*.5,.80,.06,-.25,0,.17,h,.18],
          [x+.34,-1.53+h*.5,.22,.05,-.2,0,.14,h,.16],
        ],[x*.52,-1.06,.0,0,-.29,0,.10,.06,.10]),i===3?COLORS.lime:COLORS.orange);
      });
      document.documentElement.dataset.renderer='webgl';
    }
    return {draw,dispose(){allocated.buffers.forEach(b=>gl.deleteBuffer(b));allocated.textures.forEach(t=>gl.deleteTexture(t));allocated.shaders.forEach(s=>gl.deleteShader(s));allocated.programs.forEach(p=>gl.deleteProgram(p));}};
  }
  function renderFallback(){document.documentElement.dataset.renderer='fallback';document.getElementById('interaction-hint').textContent='切换下方阶段查看研究路径';}
  function installGraphics(){try{if(forced.matches)throw new Error('Forced colors');if(graphics)graphics.dispose();graphics=createGraphics();return true;}catch(error){graphics=null;renderFallback();return false;}}
  const descriptions=['从完整财报出发，保留原始记录。','拆开报表，梳理企业、年度与指标。','把答案和原始依据，放回同一条研究路径。'];
  function updateControls(state){
    shell.dataset.phase=String(state.stage);shell.dataset.assembly=state.expanded?'expanded':'assembled';
    buttons.forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.phase)===state.stage)));
    toggle.setAttribute('aria-pressed',String(state.expanded));toggle.replaceChildren(document.createTextNode(state.expanded?'聚合装置':'展开装置'));
    const arrow=document.createElement('span');arrow.setAttribute('aria-hidden','true');arrow.textContent=state.expanded?'↙':'↗';toggle.appendChild(arrow);
    document.getElementById('phase-number').textContent=String(state.stage+1).padStart(2,'0');document.getElementById('phase-description').textContent=descriptions[state.stage];
    document.documentElement.dataset.motion=state.reduced?'reduced':'full';
  }
  const available=installGraphics();
  runtime=window.QMHeroRuntime.createRuntime({raf:fn=>window.requestAnimationFrame(fn),cancel:id=>window.cancelAnimationFrame(id),now:()=>performance.now(),hidden:()=>document.hidden,reduced:motion.matches||forced.matches},state=>{if(graphics)graphics.draw(state);},updateControls);
  runtime.setHealthy(available);
  buttons.forEach(button=>listen(button,'click',()=>runtime.setStage(Number(button.dataset.phase))));
  listen(toggle,'click',()=>runtime.toggle());
  listen(stageElement,'pointermove',event=>{if(coarse.matches)return;const r=stageElement.getBoundingClientRect();if(r.width&&r.height)runtime.pointer((event.clientX-r.left)/r.width*2-1,(event.clientY-r.top)/r.height*2-1);},{passive:true});
  listen(stageElement,'pointerleave',()=>runtime.pointer(0,0));
  listen(document,'visibilitychange',()=>runtime.syncVisibility());
  listen(motion,'change',()=>runtime.setReduced(motion.matches||forced.matches));
  listen(forced,'change',()=>{runtime.setReduced(motion.matches||forced.matches);runtime.setHealthy(installGraphics());});
  listen(window,'resize',()=>runtime.invalidate(),{passive:true});
  if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>runtime.setVisible(entries.some(entry=>entry.isIntersecting)),{threshold:.01});observer.observe(shell);cleanup.push(()=>observer.disconnect());}
  if('ResizeObserver' in window){const observer=new ResizeObserver(()=>runtime.invalidate());observer.observe(stageElement);cleanup.push(()=>observer.disconnect());}
  listen(canvas,'webglcontextlost',event=>{event.preventDefault();runtime.setHealthy(false);renderFallback();});
  listen(canvas,'webglcontextrestored',()=>runtime.setHealthy(installGraphics()));
  listen(window,'message',event=>{
    if(event.source!==window.parent||!event.data||event.data.type!=='streamlit:render')return;
    // Ignore all arbitrary parent data; this scene accepts no financial inputs.
    send('streamlit:setFrameHeight',{height:580});runtime.invalidate();
  });
  function dispose(){if(disposed)return;disposed=true;runtime.dispose();cleanup.splice(0).forEach(fn=>fn());if(graphics)graphics.dispose();graphics=null;}
  listen(window,'pagehide',dispose);listen(window,'beforeunload',dispose);
  window.__qmImmersiveHero={version:'2026-10-05.2',getState:()=>runtime.getState(),dispose};
  send('streamlit:componentReady',{apiVersion:1});send('streamlit:setFrameHeight',{height:580});
})();
