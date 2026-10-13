/* Local WebGL spatial navigation. Only explicit user intents leave the iframe. */
(function () {
  'use strict';
  const canvas=document.getElementById('sculpture');
  const shell=document.getElementById('hero');
  const stageElement=document.getElementById('sculpture-stage');
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  const coarse=window.matchMedia('(pointer: coarse)');
  const forced=window.matchMedia('(forced-colors: active)');
  const cleanup=[];
  const qualityLabel=document.getElementById('quality-status');
  const quality=window.QMHeroQuality.createQuality(state=>{
    shell.dataset.qualityTier=String(state.tier);
    qualityLabel.title=['自动画质 · 完整清晰度','自动画质 · 均衡清晰度','自动画质 · 优先流畅'][state.tier]+'，全部动作与装置细节保留';
  });
  let graphics=null, runtime=null, navigation=null, hoveredAction=null, disposed=false, presentation=true, onscreen=true,lastCamera=null,landing=false;
  const quiet=()=>!presentation||motion.matches||forced.matches;
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
  function lookAt(eye,target,roll){
    const normalize=v=>{const length=Math.hypot(...v)||1;return v.map(value=>value/length);};
    const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    const dot=(a,b)=>a.reduce((sum,value,index)=>sum+value*b[index],0);
    const back=normalize(eye.map((value,index)=>value-target[index]));
    const right=normalize(cross([0,1,0],back)),up=cross(back,right);
    const view=new Float32Array([right[0],up[0],back[0],0,right[1],up[1],back[1],0,right[2],up[2],back[2],0,-dot(right,eye),-dot(up,eye),-dot(back,eye),1]);
    return mul(rotateZ(roll),view);
  }
  const mix=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
  const clamp01=value=>Math.max(0,Math.min(1,value));
  const smooth=value=>{const t=clamp01(value);return t*t*(3-2*t);};
  const COLORS={blue:[.141,.329,1],paper:[.957,.937,.875],silver:[.65,.71,.79],orange:[.90,.47,.27],lime:[.84,.95,.31],ink:[.063,.102,.180]};
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
    const out=[],segments=128,sides=10;
    function vertex(i,j){const a=start+arc*i/segments,b=Math.PI*2*j/sides,c=Math.cos(a),s=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b);return [c*(radius+tube*cb),s*(radius+tube*cb),tube*sb,c*cb,s*cb,sb,0,0,0];}
    for(let i=0;i<segments;i++)for(let j=0;j<sides;j++)out.push(...vertex(i,j),...vertex(i+1,j),...vertex(i+1,j+1),...vertex(i,j),...vertex(i+1,j+1),...vertex(i,j+1));
    return new Float32Array(out);
  }
  function makeTexture(kind){
    const sheet=document.createElement('canvas');sheet.width=512;sheet.height=720;const c=sheet.getContext('2d');
    if(!c)throw new Error('Texture canvas unavailable');
    const blue=kind==='cover',lime=kind==='index',answer=kind==='answer';
    c.fillStyle=blue?'#2454ff':lime?(landing?'#d6f24f':'#d9d8cc'):answer?(landing?'#f2f6ff':'#f4efdf'):(landing?'#edf2fc':'#eee9d9');c.fillRect(0,0,512,720);
    // Fixed, low-contrast fibres: the material is visible without moving the type.
    let seed=271828;for(let i=0;i<5200;i++){seed=(seed*1664525+1013904223)>>>0;const x=seed%512;seed=(seed*1664525+1013904223)>>>0;const y=seed%720;c.fillStyle=i%2?'#ffffff0b':'#07172b08';c.fillRect(x,y,1+(i%3),1);}
    const spine=c.createLinearGradient(0,0,40,0);spine.addColorStop(0,'#07172b42');spine.addColorStop(.36,'#07172b0c');spine.addColorStop(.46,'#ffffff24');spine.addColorStop(1,'#ffffff00');c.fillStyle=spine;c.fillRect(0,0,40,720);
    c.strokeStyle=blue?'#b6c9ff66':'#ffffff99';c.lineWidth=1.5;c.strokeRect(1.5,1.5,509,717);
    c.fillStyle=blue?'#f4efdf':'#101a2e';c.font='500 20px Arial';c.fillText(blue?'ANNUAL REPORT':lime?'SOURCE INDEX':answer?'RESEARCH EVIDENCE':'FINANCIAL RECORDS',42,61);
    c.fillStyle=blue?'#f4efdf':'#101a2e';c.font='600 58px "Microsoft YaHei",sans-serif';
    c.fillText(blue?'年度':lime?'原始':answer?'答案':'结构化',39,180);c.fillText(blue?'报告':lime?'依据':answer?'与依据':'数据',39,248);
    c.strokeStyle=blue?'#8ba8ff':'#152b4555';c.lineWidth=2;c.beginPath();c.moveTo(42,298);c.lineTo(469,298);c.stroke();
    if(blue){
      c.strokeStyle='#bac7e8';c.lineWidth=4;c.beginPath();c.moveTo(45,522);c.lineTo(139,453);c.lineTo(239,475);c.lineTo(332,378);c.lineTo(465,412);c.stroke();
      c.fillStyle='#d6f24f';c.beginPath();c.arc(465,412,8,0,Math.PI*2);c.fill();
      c.font='22px "Microsoft YaHei",sans-serif';c.fillStyle='#e7edff';c.fillText('从记录，走向有据的答案。',42,628);
    }else if(answer||lime){
      c.font='23px "Microsoft YaHei",sans-serif';c.fillStyle='#20314a';['企业 · 年度 · 指标','原始记录 · 来源定位','口径与证据相互对应'].forEach((text,i)=>{c.fillText(text,42,375+i*67);c.fillStyle='#17273e33';c.fillRect(42,394+i*67,425,2);c.fillStyle='#20314a';});
      c.font='18px "Microsoft YaHei",sans-serif';c.fillText(answer?'打开答案与来源':'查阅原始资料',42,648);
      c.fillStyle=lime?'#e67945':'#2454ff';c.fillRect(42,680,lime?34:112,7);
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
    function release(){
      allocated.buffers.splice(0).forEach(value=>gl.deleteBuffer(value));
      allocated.textures.splice(0).forEach(value=>gl.deleteTexture(value));
      allocated.shaders.splice(0).forEach(value=>gl.deleteShader(value));
      allocated.programs.splice(0).forEach(value=>gl.deleteProgram(value));
    }
    try {
    function shader(type,source){const s=gl.createShader(type);allocated.shaders.push(s);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('Shader unavailable');return s;}
    const vs=shader(gl.VERTEX_SHADER,`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUV;attribute float aFront;uniform mat4 uModel;uniform mat3 uNormal;uniform mat4 uVP;varying vec3 vNormal;varying vec3 vPosition;varying vec2 vUV;varying float vFront;void main(){vec4 world=uModel*vec4(aPosition,1.0);vPosition=world.xyz;vNormal=normalize(uNormal*aNormal);vUV=aUV;vFront=aFront;gl_Position=uVP*world;}`);
    const fs=shader(gl.FRAGMENT_SHADER,`precision mediump float;
uniform vec3 uColor;uniform sampler2D uTexture;uniform float uHasTexture;uniform float uRoughness;uniform vec3 uEye;uniform float uTime;uniform float uChapter;uniform float uFocus;
varying vec3 vNormal;varying vec3 vPosition;varying vec2 vUV;varying float vFront;
void main(){
  vec3 base=uColor;bool face=uHasTexture>0.5&&vFront>0.5;if(face)base=texture2D(uTexture,vUV).rgb;
  vec3 n=normalize(vNormal),view=normalize(uEye-vPosition);
  vec3 key=normalize(vec3(-4.8+uChapter*3.8+sin(uTime*0.21)*1.1,5.2,6.0)-vPosition),fill=normalize(vec3(4.5,1.4,2.0)-vPosition);
  vec3 rim=normalize(vec3(1.8,3.2,-4.2)-vPosition);
  float diffuse=max(dot(n,key),0.0),bounce=max(dot(n,fill),0.0);
  float gloss=pow(max(dot(n,normalize(key+view)),0.0),mix(100.0,12.0,uRoughness));
  float softbox=pow(max(dot(n,normalize(fill+view)),0.0),18.0);
  float fresnel=pow(1.0-max(dot(n,view),0.0),3.0);
  vec3 color=base*(0.44+0.48*diffuse)+base*vec3(0.69,0.80,1.0)*bounce*0.20;
  color+=vec3(1.0,0.94,0.80)*gloss*(1.0-uRoughness)*0.52;
  color+=vec3(0.68,0.82,1.0)*(softbox*0.10+fresnel*0.10);
  color+=mix(vec3(0.48,0.69,1.0),vec3(1.0,0.68,0.35),uChapter*.5)*pow(max(dot(n,rim),0.0),2.0)*(1.0-uRoughness)*0.24;
  if(face){float edge=min(min(vUV.x,1.0-vUV.x),min(vUV.y,1.0-vUV.y));color+=vec3(0.62,0.75,0.98)*(1.0-smoothstep(0.0,0.006,edge))*0.14;}
  color+=vec3(0.12,0.17,0.22)*uFocus;
  gl_FragColor=vec4(color,1.0);
}`);
    const program=gl.createProgram();allocated.programs.push(program);gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Program unavailable');gl.useProgram(program);
    const attr={};['Position','Normal','UV','Front'].forEach(name=>attr[name]=gl.getAttribLocation(program,'a'+name));
    const uni={};['Model','Normal','VP','Color','Texture','HasTexture','Eye','Roughness','Time','Chapter','Focus'].forEach(name=>uni[name]=gl.getUniformLocation(program,'u'+name));
    function buffer(data,usage=gl.STATIC_DRAW){const value=gl.createBuffer();allocated.buffers.push(value);gl.bindBuffer(gl.ARRAY_BUFFER,value);gl.bufferData(gl.ARRAY_BUFFER,data,usage);return {value,count:data.length/9};}
    const cube=buffer(cubeVertices()),ring=buffer(torusVertices(2.15,.007)),ribbon=buffer(torusVertices(2.20,.013,-.25,Math.PI*.24));
    const tracer=buffer(torusVertices(2.28,.007,.1,Math.PI*.40));
    const sheet=window.QMHeroPaper.createGeometry(),paper=buffer(sheet.data,gl.DYNAMIC_DRAW);
    paper.indices=gl.createBuffer();allocated.buffers.push(paper.indices);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,paper.indices);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,sheet.indices,gl.STATIC_DRAW);paper.count=sheet.indices.length;
    let paperSignature='';
    const textures={};['cover','paper','answer','index'].forEach(kind=>{const texture=gl.createTexture();allocated.textures.push(texture);gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,makeTexture(kind));gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);textures[kind]=texture;});
    gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);gl.clearColor(0,0,0,0);
    const surfacePool=[];let surfaceCount=0,selectionPose=null;
    function mesh(geometry,matrix,color,texture,flex,action=null){
      const selected=action&&selectionPose?.action===action?selectionPose:null;
      if(selected)matrix=mul(translate(0,selected.lift*.14,selected.lift),mul(matrix,mul(rotateZ(selected.turn),scale(selected.scale,selected.scale,1))));
      gl.bindBuffer(gl.ARRAY_BUFFER,geometry.value);const stride=9*4;
      const size=[Math.hypot(matrix[0],matrix[1],matrix[2]),Math.hypot(matrix[4],matrix[5],matrix[6]),Math.hypot(matrix[8],matrix[9],matrix[10])];
      const normal=new Float32Array([matrix[0]/(size[0]*size[0]),matrix[1]/(size[0]*size[0]),matrix[2]/(size[0]*size[0]),matrix[4]/(size[1]*size[1]),matrix[5]/(size[1]*size[1]),matrix[6]/(size[1]*size[1]),matrix[8]/(size[2]*size[2]),matrix[9]/(size[2]*size[2]),matrix[10]/(size[2]*size[2])]);
      if(geometry===paper){
        const signature=size.join(',')+','+flex.join(',');
        if(signature!==paperSignature){gl.bufferSubData(gl.ARRAY_BUFFER,0,window.QMHeroPaper.deform(sheet,size,flex[0],flex[1]));paperSignature=signature;}
        if(navigation?.ready&&action){
          const surface=surfacePool[surfaceCount]||(surfacePool[surfaceCount]={vertices:new Float32Array(sheet.data.length),matrix:new Float32Array(16),indices:sheet.indices});
          surface.action=action;surface.matrix.set(matrix);surface.vertices.set(sheet.data);surfaceCount++;
        }
      }
      [['Position',3,0],['Normal',3,12],['UV',2,24],['Front',1,32]].forEach(([name,size,offset])=>{gl.enableVertexAttribArray(attr[name]);gl.vertexAttribPointer(attr[name],size,gl.FLOAT,false,stride,offset);});
      gl.uniformMatrix4fv(uni.Model,false,matrix);gl.uniformMatrix3fv(uni.Normal,false,normal);gl.uniform3fv(uni.Color,color);gl.uniform1f(uni.HasTexture,texture?1:0);gl.uniform1f(uni.Roughness,texture===textures.cover?.30:texture?.76:.24);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,texture||textures.paper);gl.uniform1i(uni.Texture,0);
      gl.uniform1f(uni.Focus,selected?selected.glow:action&&hoveredAction===action?.65:0);
      if(geometry.indices){gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,geometry.indices);gl.drawElements(gl.TRIANGLES,geometry.count,gl.UNSIGNED_SHORT,0);}
      else gl.drawArrays(gl.TRIANGLES,0,geometry.count);
    }
    function draw(state){
      surfaceCount=0;selectionPose=state.selection;
      const rect=canvas.getBoundingClientRect(),ratio=quality.ratio(window.devicePixelRatio),width=Math.max(1,Math.round(rect.width*ratio)),height=Math.max(1,Math.round(rect.height*ratio));
      if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
      gl.viewport(0,0,width,height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
      const aspect=width/height;
      const open=smooth(state.open),unfold=1-open,time=state.reduced?0:state.time;
      const px=state.pointer[0],py=state.pointer[1],idle=state.reduced?0:Math.sin(time*.38)*.055;
      const chapter=state.stage-1;
      const score=state.choreography||{fan:0,passage:0,gather:smooth(state.stage-1),archive:0,energy:.25};
      // A real camera travels through the existing paper sculpture. The close
      // shots intentionally crop the surrounding objects, then settle to a
      // fully framed composition. Text planes themselves never tumble.
      const cue=state.camera,distance=(state.landing?Math.max(7.95,5.8/aspect):Math.max(8.05,9.3/aspect))*cue[0];
      const yaw=cue[4]+px*.12,pitch=cue[5]+py*.065;
      const target=[cue[1],cue[2],cue[3]],eye=[
        target[0]+Math.sin(yaw)*Math.cos(pitch)*distance,
        target[1]+Math.sin(pitch)*distance,
        target[2]+Math.cos(yaw)*Math.cos(pitch)*distance,
      ];
      const projection=perspective(cue[7],aspect,.1,60),view=lookAt(eye,target,cue[6]);
      lastCamera={eye:eye.slice(),target:target.slice(),distance,fov:cue[7],shot:state.shot};
      const viewProjection=mul(projection,view);
      gl.uniformMatrix4fv(uni.VP,false,viewProjection);gl.uniform3fv(uni.Eye,eye);
      gl.uniform1f(uni.Time,time);gl.uniform1f(uni.Chapter,state.stage);
      if(state.landing){
        // This is the same closed, deforming paper mesh and texture stack as
        // the workspace. Its fullscreen pose and lens form a separate scene.
        const reveal=state.landingPose,spread=reveal.spread,flow=reveal.flow,flight=reveal.travel,exit=reveal.exit;
        const compact=aspect<1.1;
        const center=compact?[3.35,-.2,-1.8]:[2.22,.18,0];
        const rotation=-.22+Math.sin(time*.17)*.075+reveal.turn*.05;
        const group=mul(translate(center[0]+px*.16,center[1]-py*.11,center[2]+exit*1.6),mul(rotateY(-.10+Math.sin(time*.13)*.10),rotateZ(rotation)));
        const cold=[.935,.953,.985],silver=[.69,.76,.86];
        function leaf(position,texture,color,layer,action){
          const p=position.slice();p[0]+=flight*(layer%2?2:-1.2);p[1]+=flight*(layer-3)*.24;
          p[2]+=flight*(3-layer*.42);p[4]+=flight*.48;p[5]+=(1-spread)*(layer-3)*.11;
          p[1]+=Math.sin(time*.46+layer*.7)*.065;p[2]+=Math.sin(time*.31+layer*.8)*.09;
          if(action==='annual_data'){p[0]+=(layer-3)*reveal.fan*.19;p[1]+=(layer-3)*reveal.fan*.15;p[2]+=(layer-3)*reveal.fan*.18;p[5]+=(layer-3)*reveal.fan*.045;}
          if(action==='answer_evidence'){p[0]-=reveal.detail*.19;p[1]+=reveal.lift*.30;p[2]+=reveal.detail*.32;p[5]-=reveal.detail*.16;}
          mesh(paper,mul(group,model(p)),color,texture,state.paperFlex[layer],action);
        }
        for(let i=0;i<5;i++){
          const n=i-2;
          leaf([-.53+n*.30*spread,-.04+n*.20*spread,-.75+i*.13,-.12+n*.10,-.44+n*.07+flow*.12,-.05+n*.18*spread,
            2.02,2.98,.025],i===4?textures.paper:null,i%2?cold:silver,i+1,'annual_data');
        }
        leaf([-.48+flow*.13,.16,.58,-.08,-.22+flow*.06,-.08,2.19,3.19,.075],textures.cover,COLORS.blue,0,'annual_reports');
        leaf([1.05+flow*.16,-.91,.93,.12,.19-flow*.12,.24,1.32,1.86,.048],textures.answer,cold,3,'answer_evidence');
        leaf([1.10,.99,-.27,-.16,.24,.24,1.00,1.40,.032],textures.index,COLORS.lime,5,'annual_reports');
        const orbit=mul(translate(center[0],center[1]-.08,center[2]-.45),mul(rotateZ(-.34+flow*.06),mul(rotateX(.86+Math.sin(time*.16)*.18),scale(1.66,1.66,1.66))));
        mesh(ring,orbit,silver);mesh(ribbon,mul(orbit,rotateZ(.4+time*.19)),COLORS.lime);mesh(tracer,mul(orbit,rotateZ(2.1-time*.14)),[.46,.62,1]);
        mesh(ring,mul(translate(center[0]+.18,center[1],center[2]-.9),mul(rotateY(1.04+flow*.10),mul(rotateZ(.18-time*.021),scale(1.50,1.50,1.50)))),[.36,.46,.68]);
        // A single passing evidence filament joins the data sheet and the
        // answer card. Abstract geometry is never presented as a real metric.
        for(let i=0;i<18;i++){
          const t=i/18,t2=(i+1)/18;
          const point=n=>[center[0]-1.95+n*3.6,center[1]-1.36+Math.sin(n*Math.PI)*.45,center[2]+.2+Math.sin(n*Math.PI)*1.1];
          const a=point(t),b=point(t2),d=b.map((v,k)=>v-a[k]),length=Math.hypot(...d),h=Math.hypot(d[0],d[1]);
          mesh(cube,model([...(a.map((v,k)=>(v+b[k])*.5)),0,-Math.atan2(d[2],h),Math.atan2(d[1],d[0]),length+.002,.012,.012]),i===17?COLORS.lime:silver);
        }
        document.documentElement.dataset.renderer='webgl';navigation?.setScene(surfacePool.slice(0,surfaceCount),viewProjection,rect);return;
      }
      function pose(poses,closed,layer=0){
        const phase=state.layers[layer],spread=smooth(state.spreads[layer]);
        const blend=phase<1?phase:phase-1,first=phase<1?0:1,second=first+1;
        const p=mix(poses[first],poses[second],blend),q=mix(closed,p,spread);
        // Offset paper layers follow the same reversible path at different
        // rates. No spring overshoot or independent queued entrance timelines.
        if(!state.reduced){
          q[1]+=Math.sin(time*.58+layer*.62+q[0])*.048*spread;
          q[2]+=Math.sin(spread*Math.PI)*(.16+layer*.018);
          q[5]+=Math.sin(time*.33+layer*.4)*.012*spread;
          // The same physical sheets fan apart, make a camera corridor, then
          // return as an archive. Cover and paper keep their own thickness.
          q[0]+=(layer-4)*.075*score.fan*spread;
          q[2]+=(layer-4)*.075*score.fan*spread;
          q[5]+=(layer-4)*.019*score.fan*spread;
          q[0]+=(layer%2?-.14:.14)*score.passage*spread;
          q[2]-=score.archive*.10*spread;
        }
        return model(q);
      }
      // Every dimension and line is an illustrative object, never a financial value.
      for(let i=0;i<5;i++){
        const closed=[-.15+i*.026,.04+i*.009,-.08+i*.045,-.09,-.29,-.14,1.60,2.28,.028];
        const poses=[
          [-.34-i*.22,.08+i*.105,-.20-i*.17,-.1,-.35,-.16-i*.11,1.60,2.28,.028],
          [-1.32+i*.63,.07+(i%2)*.26,-.88+i*.35,-.31+i*.09,-.56+i*.20,-.56+i*.26,1.32,1.96,.028],
          [-1.13-i*.08,.05+i*.035,-.17-i*.10,-.05,-.20,-.09-i*.03,1.32,1.96,.028],
        ];
        mesh(paper,pose(poses,closed,i+1),i%2?COLORS.paper:COLORS.silver,i===4?textures.paper:null,state.paperFlex[i+1],'annual_data');
      }
      mesh(paper,pose([
        [.06,-.05,.65,-.07,-.32,-.19,1.65,2.32,.072],
        [-1.33,-.07,.84,-.13,-.45,-.38,1.44,2.13,.072],
        [-1.05,.04,.36,-.1,-.32,-.16,1.53,2.20,.072],
      ],[-.13,.01,.29,-.09,-.29,-.14,1.65,2.32,.072]),COLORS.blue,textures.cover,state.paperFlex[0],'annual_reports');
      mesh(paper,pose([
        [1.27,-.43,-.14,.10,.28,.19,.74,1.10,.042],
        [1.56,-.34,.66,.12,.30,.24,.81,1.23,.042],
        [.91,-.06,.90,.02,-.05,.065,1.58,2.16,.065],
      ],[.01,.01,-.18,-.09,-.29,-.14,1.48,2.18,.04],3),COLORS.paper,textures.answer,state.paperFlex[3],'answer_evidence');
      mesh(paper,pose([
        [.80,.97,-.22,-.18,.38,.26,.48,.68,.025],
        [.95,1.08,-.20,-.18,.23,.12,.48,.68,.025],
        [.63,1.12,-.28,-.12,.10,-.02,.48,.68,.025],
      ],[.04,.02,-.24,-.09,-.29,-.14,1.40,2.08,.035],5),COLORS.lime,textures.index,state.paperFlex[5],'annual_reports');
      const orbitOpen=.60+.40*open;
      const orbit=mul(translate(0,-.02,-.2),mul(rotateZ(-.34+idle*.5),mul(rotateX(.89+idle+unfold*.22),scale(orbitOpen,orbitOpen,orbitOpen))));
      mesh(ring,orbit,[.62,.68,.77]);
      mesh(ribbon,mul(orbit,rotateZ(.4+time*.28+score.energy*.7)),COLORS.lime);
      mesh(tracer,mul(orbit,rotateZ(2.6-time*.19)),[.31,.44,.75]);
      mesh(ring,mul(translate(.03,.12,-.24),mul(rotateZ(.27),mul(rotateX(1.10),scale(orbitOpen*.91,orbitOpen*.91,orbitOpen*.91)))),[.35,.41,.54]);
      // Small solid markers travel on the same orbit as the report index.
      // These are geometric product illustrations, never measured data points.
      for(let i=0;i<1;i++){
        const angle=time*.28+i*2.094+.4;
        const marker=mul(orbit,mul(translate(Math.cos(angle)*2.15,Math.sin(angle)*2.15,0),rotateZ(angle)));
        mesh(cube,mul(marker,scale(.065,.065,.045)),COLORS.lime);
      }
      // Four solid data bars re-form below the papers as the structure opens.
      [0,1,2,3].forEach(i=>{
        const h=[.35,.59,.46,.82][i],x=-.34+i*.25;
        mesh(cube,pose([
          [x,-1.60+h*.5,.25,0,-.18,0,.14,h,.16],
          [x+.34,-1.52+h*.5,.80,.06,-.25,0,.17,h,.18],
          [x+.34,-1.53+h*.5,.22,.05,-.2,0,.14,h,.16],
        ],[x*.52,-1.06,.0,0,-.29,0,.10,.06,.10],i+2),i===3?COLORS.paper:COLORS.blue);
      });
      // The second act extracts solid light fragments through an open lens.
      // These abstract paths never take real values, query progress or results.
      const extraction=smooth(1-Math.abs(state.stage-1))*open;
      const resolution=smooth(state.stage-1)*open;
      const lens=mul(translate(.12,-.08,1.08),mul(rotateY(.26+chapter*.12),mul(rotateX(.16),scale(.54,.54,.54))));
      mesh(tracer,mul(lens,rotateZ(-time*.48)),COLORS.silver);
      // One continuous evidence filament, not independent confetti. Each
      // segment keeps its identity while the curve gathers onto the card.
      const point=t=>{
        const curve=Math.sin(t*Math.PI),gather=score.gather;
        return mix([-1.25+t*2.7,.44-1.12*t+curve*.58,.72+curve*.73],
          [.35+t*1.12,-.72+t*.055,1.03],gather);
      };
      for(let i=0;i<16;i++){
        const a=point(i/16),b=point((i+1)/16),delta=b.map((v,k)=>v-a[k]);
        const length=Math.hypot(...delta),horizontal=Math.hypot(delta[0],delta[1]);
        const center=a.map((v,k)=>(v+b[k])*.5),width=.004+(extraction+resolution)*.005;
        mesh(cube,model([...center,0,-Math.atan2(delta[2],horizontal),Math.atan2(delta[1],delta[0]),length+.002,width,width]),i===15?COLORS.lime:COLORS.silver);
      }
      // An exact geometric frame draws attention to the final evidence card.
      // Its visibility follows the same pose and reverses without a new timer.
      const bracketSize=.002+resolution*.018;
      for(const side of [-1,1])for(const vertical of [-1,1]){
        const anchor=mul(model([.91,-.06,.94,.02,-.05,.065,1,1,1]),translate(side*.83,vertical*1.12,.025));
        mesh(cube,mul(anchor,mul(translate(-side*.10,0,0),scale(.22,bracketSize,bracketSize))),COLORS.silver);
        mesh(cube,mul(anchor,mul(translate(0,-vertical*.10,0),scale(bracketSize,.22,bracketSize))),COLORS.silver);
      }
      document.documentElement.dataset.renderer='webgl';
      navigation?.setScene(surfacePool.slice(0,surfaceCount),viewProjection,rect);
    }
    return {draw,dispose:release,getPaperState:()=>({vertices:sheet.data.length/9,triangles:sheet.indices.length/3,columns:sheet.columns,rows:sheet.rows,closed:true,instances:8})};
    } catch(error) { release(); throw error; }
  }
  function renderFallback(){document.documentElement.dataset.renderer='fallback';document.getElementById('interaction-hint').textContent='使用下方研究入口继续';navigation?.setScene([],null,null);}
  function installGraphics(){
    if(graphics)graphics.dispose();graphics=null;
    try{if(forced.matches)throw new Error('Forced colors');graphics=createGraphics();return true;}
    catch(error){renderFallback();return false;}
  }
  const descriptions=['点击蓝色封面，查阅年度报告。','点击纸张数据层，查看企业年度指标。','点击答案卡，打开当前答案与来源。'];
  function updateControls(state){
    shell.dataset.phase=String(state.stage);shell.dataset.assembly=state.expanded?'expanded':'assembled';
    document.getElementById('phase-number').textContent=String(state.stage+1).padStart(2,'0');
    const description=document.getElementById('phase-description');
    if(description.textContent!==descriptions[state.stage])description.textContent=descriptions[state.stage];
    document.documentElement.dataset.motion=state.reduced?'reduced':'full';
    shell.dataset.playback=state.playback;
  }
  function portalIntent(event,rect,label){
    if(!rect||![rect.left,rect.top,rect.width,rect.height].every(Number.isFinite))return;
    const width=window.innerWidth||canvas.getBoundingClientRect().width,height=window.innerHeight||580;
    const left=Math.max(0,rect.left),top=Math.max(0,rect.top),right=Math.min(width,rect.left+rect.width),bottom=Math.min(height,rect.top+rect.height);
    if(right<=left||bottom<=top)return;
    let origin;try{origin=new URL(document.referrer).origin;}catch(error){origin=window.location?.origin;}
    if(!origin||origin==='null')return;
    window.parent.postMessage({type:'qm:portal-intent',...event,label,rect:{left,top,width:right-left,height:bottom-top}},origin);
  }
  navigation=window.QMHeroNavigation?.createNavigation({document,shell,listen,
    onHover(action){hoveredAction=action;runtime?.invalidate();},cancel(){runtime?.cancelSelection();},
    begin(action,done){if(!runtime||quiet()||!graphics)done();else runtime.selectObject(action,done);},
    intent:portalIntent,emit(event){send('streamlit:setComponentValue',{value:event,dataType:'json'});}
  })||null;
  let available=installGraphics();
  function startRuntime(){
    // The first parent render supplies the actual preference. Starting in a
    // temporary reduced state would consume the opening before it can animate.
    const owner=landing&&window.QMLandingCinema?window.QMLandingCinema:window.QMHeroRuntime;
    runtime=owner.createRuntime({document,shell,autoplay:true,raf:fn=>window.requestAnimationFrame(fn),cancel:id=>window.cancelAnimationFrame(id),now:()=>performance.now(),hidden:()=>document.hidden,reduced:quiet(),onFrame:(now,eligible)=>quality.sample(now,eligible),onPause:()=>quality.pause()},state=>{if(graphics)graphics.draw(state);},updateControls);
    runtime.setHealthy(available);runtime.setVisible(onscreen);
  }
  listen(stageElement,'pointermove',event=>{navigation?.hoverAt(event.clientX,event.clientY);if(coarse.matches)return;const r=stageElement.getBoundingClientRect();if(r.width&&r.height)runtime?.pointer((event.clientX-r.left)/r.width*2-1,(event.clientY-r.top)/r.height*2-1);},{passive:true});
  listen(stageElement,'pointerleave',()=>{runtime?.pointer(0,0);navigation?.clearHover();});
  listen(stageElement,'click',event=>{if(event.button&&event.button!==0)return;navigation?.selectAt(event.clientX,event.clientY);});
  listen(document,'visibilitychange',()=>runtime?.syncVisibility());
  listen(motion,'change',()=>runtime?.setReduced(quiet()));
  listen(forced,'change',()=>{available=installGraphics();runtime?.setReduced(quiet());runtime?.setHealthy(available);});
  listen(window,'resize',()=>{if(landing)send('streamlit:setFrameHeight',{height:window.innerHeight});runtime?.invalidate();},{passive:true});
  if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{onscreen=entries.some(entry=>entry.isIntersecting);runtime?.setVisible(onscreen);},{threshold:.01});observer.observe(shell);cleanup.push(()=>observer.disconnect());}
  if('ResizeObserver' in window){const observer=new ResizeObserver(()=>runtime?.invalidate());observer.observe(stageElement);cleanup.push(()=>observer.disconnect());}
  listen(canvas,'webglcontextlost',event=>{event.preventDefault();available=false;runtime?.setHealthy(false);renderFallback();navigation?.settlePending();});
  listen(canvas,'webglcontextrestored',()=>{available=installGraphics();runtime?.setHealthy(available);});
  listen(window,'message',event=>{
    if(disposed||event.source!==window.parent||!event.data||event.data.type!=='streamlit:render')return;
    // Accept only the shared visual preference; this scene accepts no financial inputs.
    const preference=event.data.args?.motion,next=preference==null||(preference.version===1&&preference.mode==='presentation');
    const nextLanding=event.data.args?.landing===true;
    if(nextLanding!==landing){runtime?.dispose();runtime=null;landing=nextLanding;navigation?.setLanding(landing);available=installGraphics();}
    window.QMLandingCinema?.setLayout(document,shell,landing,event.data.args?.brand);
    navigation?.setContext(event.data.args?.context);
    if(!runtime){presentation=next;startRuntime();}
    else if(next!==presentation){presentation=next;runtime.setReduced(quiet());}
    send('streamlit:setFrameHeight',{height:landing?window.innerHeight:580});runtime.invalidate();
  });
  function dispose(){if(disposed)return;disposed=true;navigation?.dispose();runtime?.dispose();quality.dispose();cleanup.splice(0).forEach(fn=>fn());if(graphics)graphics.dispose();graphics=null;}
  listen(window,'pagehide',dispose);listen(window,'beforeunload',dispose);
  window.__qmImmersiveHero={version:'2026-10-11.24',getState:()=>Object.assign(runtime?runtime.getState():{ready:false,disposed},{landing,navigation:navigation?.getState(),quality:quality.getState(),paperGeometry:graphics?.getPaperState(),cameraRig:lastCamera?{...lastCamera,eye:lastCamera.eye.slice(),target:lastCamera.target.slice()}:null}),getNavigationTargets:()=>navigation?.getTargets()||[],hitTest:(x,y)=>navigation?.hitTest(x,y)||null,dispose};
  send('streamlit:componentReady',{apiVersion:1});send('streamlit:setFrameHeight',{height:580});
})();
