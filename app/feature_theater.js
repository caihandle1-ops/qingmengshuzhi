/* Local, automatically revealed concept scenes. Trusted static artwork is constructed here
   because Streamlit's HTML-only sanitizer intentionally removes inline SVG.
   No financial values, analysis state, storage, network or Streamlit events. */
(function installFeatureTheater(win) {
  'use strict';
  if (!win?.document) return;
  const VERSION = '2026-10-11.22-spatial-editions';
  if (win.QMFeatureTheater?.version === VERSION && !win.QMFeatureTheater.disposed) return;
  win.QMFeatureTheater?.dispose();
  const doc = win.document;
  const media = win.matchMedia?.('(prefers-reduced-motion: reduce)');
  const quiet = () => Boolean(media?.matches) || doc.documentElement.dataset.qmMotionMode === 'research';
  const route = () => {
    const header = doc.querySelector('[data-studio-scene]');
    return header ? header.getAttribute('data-studio-scene') + '|' + header.getAttribute('data-studio-location') : '';
  };
  const FILE = 'M-68-94 H34 L68-59 V94 H-68 Z';
  const DIAMOND = 'M0-102 L95-4 L0 102 L-95-4 Z';
  const FRAME = 'M-89-63 H89 V63 H-89 Z';
  const LENS = 'M0-78 C43-78 78-43 78 0 C78 43 43 78 0 78 C-43 78-78 43-78 0 C-78-43-43-78 0-78 Z';
  const TRIANGLE = 'M-62-85 L94 0 L-62 85 Z';
  const HEX = 'M0-96 L83-48 L83 48 L0 96 L-83 48 L-83-48 Z';
  const BUBBLE = 'M-90-58 H90 V46 H-32 L-66 80 V46 H-90 Z';
  const SPECS = {
    qa: {name:'财报问数', title:'一个问题，沿着依据展开。', word:'TRACE', number:'01', ink:'#153c91', paper:'#f2f6ff', accent:'#285fea', light:'#e4ee88',
      chapters:['提出问题','连接依据','组织答案'], descriptions:['把问题拆成指标、期间与对象，让研究有一个清晰的起点。','沿着数值与原文找到来处，让每条线索有迹可循。','把结论与支持它的依据放在一起，保留继续追问的入口。'],
      shapes:[BUBBLE, DIAMOND, FRAME], motion:'M120,360 C280,370 330,125 520,215 S760,375 936,170'},
    scope: {name:'口径核验', title:'让差异显现，让比较有边界。', word:'ALIGN', number:'02', ink:'#213899', paper:'#d9e4fc', accent:'#e0eb78', light:'#f2f5b8',
      chapters:['展开差异','逐项对照','界定边界'], descriptions:['把容易藏在数字背后的六个口径维度分开看。','沿着同一条参照线，检查定义、单位、期间、范围、政策与版本。','展示可比性需要的边界；动画不代表六个维度已经通过核验。'],
      shapes:[DIAMOND, FILE, FRAME], motion:'M110,360 C190,160 800,70 920,180 S730,390 510,380'},
    counter: {name:'反证核验', title:'把答案拆开，再向证据追问。', word:'RECHECK', number:'03', ink:'#4c293f', paper:'#fff0d5', accent:'#ef795d', light:'#fff1bf',
      chapters:['拆解答案','追索证据','再看一层'], descriptions:['先把候选答案与前提展开，给每一个判断留出被审视的空间。','让原件、条件与计算建立联系，沿线索找到需要核对的地方。','镜头靠近原文与计算；这里展示核验方法，不给出核验结论。'],
      shapes:[FILE, HEX, LENS], motion:'M120,356 C235,310 304,80 510,110 S760,360 948,245'},
    replay: {name:'证据复演', title:'把研究留在时间里，随时复演。', word:'REPLAY', number:'04', ink:'#4b2a71', paper:'#fbf5ff', accent:'#b899e9', light:'#fff0bd',
      chapters:['冻结条件','打开档案','沿迹复演'], descriptions:['留住当时的研究条件，让后来的回看有明确的起点。','把来源、查询与核验记录展开，按发生顺序重新建立联系。','沿着记录复看研究过程；复演的条件与结果仍以真实证据包为准。'],
      shapes:[FILE, DIAMOND, TRIANGLE], motion:'M120,360 C220,280 308,130 430,140 S620,355 760,340 S860,130 960,165'},
    assets: {name:'数据资产', title:'散落的资料，进入有序的坐标。', word:'INDEX', number:'05', ink:'#164d41', paper:'#e6f2d6', accent:'#b6db72', light:'#87c4a9',
      chapters:['展开资料','连接索引','保留来路'], descriptions:['把不同格式的资料摊开，先看清每份文件的用途与来源。','接入、复核与索引相互连接，让资料能被研究过程找到。','文件归入有出处的资料体系；图示不代表当前入库数量或处理进度。'],
      shapes:[FILE, HEX, FRAME], motion:'M100,190 C240,60 320,100 510,250 S760,395 954,300'}
  };
  function paper(key, x, y, width, height, fill, ink, title, kicker, rotation = 0) {
    const lines = title.split('|');
    return `<g transform="translate(${x} ${y}) rotate(${rotation} ${width / 2} ${height / 2})"><g data-ft-card="${key}">
      <path d="M8 11 H${width + 8} V${height + 11} H8 Z" fill="${ink}" opacity=".12"/>
      <path d="M0 0 H${width - 28} L${width} 28 V${height} H0 Z" fill="${fill}" stroke="${ink}" stroke-width="1.3"/>
      <path d="M${width - 28} 0 V28 H${width}" fill="none" stroke="${ink}" stroke-width="1" opacity=".5"/>
      <text x="20" y="31" class="ft-art-kicker" fill="${ink}">${kicker}</text>
      ${lines.map((line, i) => `<text x="20" y="${77 + i * 36}" class="ft-art-title" fill="${ink}">${line}</text>`).join('')}
      <path d="M20 ${height - 67} H${width - 20} M20 ${height - 52} H${width - 54} M20 ${height - 37} H${width - 35}" fill="none" stroke="${ink}" stroke-width="1.4" opacity=".38"/>
      <path d="M20 ${height - 17} H${width - 20}" fill="none" stroke="${ink}" stroke-width="4" opacity=".14"/>
    </g></g>`;
  }
  const tagged = (x, y, text, color) => `<g data-ft-token transform="translate(${x} ${y})"><rect x="-48" y="-17" width="96" height="34" fill="${color}"/><text text-anchor="middle" y="5" class="ft-art-copy" fill="#172a35">${text}</text></g>`;
  function artwork(scene, spec) {
    let objects = '', paths = '', marks = '';
    const core = '<g transform="translate(540 242)"><g data-ft-core-wrap><path data-ft-core class="ft-core" d="' + spec.shapes[2] + '"/><g data-ft-core-detail>';
    if (scene === 'counter') {
      objects = paper('claim',145,88,208,270,spec.accent,spec.ink,'候选|答案','CANDIDATE / 01',-10) +
        paper('evidence',736,111,215,240,spec.paper,spec.ink,'原文与|计算','SOURCE / 02',9) +
        '<g transform="translate(425 166)"><g data-ft-back-sheet><rect width="238" height="218" fill="#b76d70" opacity=".36"/><path d="M19 34 H214 M19 60 H168 M19 90 H213 M19 120 H140" stroke="#562939" stroke-width="2" opacity=".25"/></g></g>';
      paths = 'M340 216 L445 153 L540 242 L668 138 L754 216 M540 242 L390 367 L710 371 Z';
      marks = core + '<path d="M55 55 L110 110" stroke="#4c293f" stroke-width="15"/><path d="M-35-9 H35 M-35 9 H20" stroke="#4c293f" stroke-width="3"/></g></g></g>' +
        tagged(440,112,'原件',spec.paper)+tagged(687,118,'条件',spec.paper)+tagged(560,382,'计算',spec.paper);
    } else if (scene === 'qa') {
      objects = paper('question',133,97,228,237,spec.accent,'#f2f6ff','为什么|发生变化？','YOUR QUESTION',-9) +
        paper('answer',725,127,224,239,spec.paper,spec.ink,'结论|＋依据','ANSWER STRUCTURE',8);
      paths = 'M345 229 C420 125 460 151 540 242 S660 340 743 240 M360 312 L468 350 L615 350 L725 302';
      marks = core + '<path d="M-49-12 H49 M-49 8 H28 M-49 28 H39" stroke="#153c91" stroke-width="3"/></g></g></g>' +
        tagged(457,123,'期间','#f0f6ff')+tagged(640,151,'指标','#e4ee88')+tagged(588,378,'原文','#e4ee88');
    } else if (scene === 'scope') {
      const names = ['指标定义','单位币种','报告期间','合并范围','会计政策','披露版本'];
      objects = names.map((name,i) => `<g transform="translate(189 ${77 + i * 46})"><g data-ft-ruler="${i}"><rect width="323" height="34" fill="${i % 2 ? '#bdcff8' : '#e1e9ff'}"/><rect width="5" height="34" fill="#e0eb78"/><text x="17" y="22" fill="#30428c" class="ft-art-kicker">0${i+1}</text><text x="67" y="23" fill="#213899" class="ft-art-copy">${name}</text><path d="M165 8 V26 M178 13 V26 M191 13 V26 M204 8 V26 M217 13 V26 M230 13 V26 M243 8 V26 M256 13 V26 M269 13 V26 M282 8 V26 M295 13 V26" stroke="#7186be"/></g></g>`).join('');
      objects += '<g data-ft-guide><path d="M520 49 V396" stroke="#e0eb78" stroke-width="2"/><path d="M510 49 H530 M510 396 H530" stroke="#e0eb78" stroke-width="2"/></g>';
      paths = 'M529 104 L692 165 M529 241 L692 241 M529 366 L692 317';
      marks = '<g transform="translate(765 237)"><g data-ft-core-wrap><path data-ft-core class="ft-core" d="'+spec.shapes[2]+'"/><g data-ft-core-detail><path d="M-62-38 H62 V38 H-62 Z M0-38 V38" fill="none" stroke="#213899" stroke-width="2"/></g></g></g><text x="700" y="113" class="ft-art-kicker" fill="#e1e9ff">CONTEXT / 六个维度</text><text x="701" y="370" class="ft-art-copy" fill="#e1e9ff">先明确边界，再比较数值。</text>';
    } else if (scene === 'replay') {
      objects = '<g data-ft-film><path d="M82 122 H1007 V366 H82 Z" fill="#4b2a71"/>' + Array.from({length:19},(_,i)=>`<path d="M${100+i*47} 132 h23 v10 h-23 Z M${100+i*47} 346 h23 v10 h-23 Z" fill="#d5bee9"/>`).join('') + '</g>' +
        paper('context',150,71,207,266,spec.paper,spec.ink,'条件|快照','01 / CONTEXT',-8)+
        paper('sources',440,113,209,244,'#c3a5ec',spec.ink,'来源|记录','02 / SOURCES',3)+
        paper('recheck',749,65,212,269,spec.paper,spec.ink,'离线|复算','03 / RECHECK',10);
      paths = 'M251 393 H842';
      marks = '<g transform="translate(672 253)"><g data-ft-core-wrap><path data-ft-core class="ft-core" d="'+spec.shapes[2]+'" transform="scale(.40)"/><g data-ft-core-detail><path d="M-32 47 H32" stroke="#4b2a71" stroke-width="3"/></g></g></g><g data-ft-playhead><path d="M251 389 V401" stroke="#4b2a71" stroke-width="6"/></g>';
    } else {
      objects = '<g data-ft-index><path d="M136 327 H965 V402 H136 Z" fill="#e6f2d6"/><path d="M136 327 H965" stroke="#b6db72" stroke-width="7"/><text x="158" y="357" fill="#164d41" class="ft-art-kicker">RESEARCH INDEX / 资料索引</text><text x="158" y="384" fill="#164d41" class="ft-art-copy">来源、版本与研究用途，始终可以追溯。</text><path d="M723 351 H935 M723 365 H935 M723 379 H850" stroke="#689f7d" stroke-width="2"/></g>' +
        paper('csv',140,111,165,207,'#edf0bc',spec.ink,'CSV','STRUCTURED',-18)+
        paper('xlsx',342,75,165,219,'#a5d8b4',spec.ink,'XLSX','WORKBOOK',-6)+
        paper('pdf',568,66,165,223,'#76b79b',spec.ink,'PDF','ORIGINAL',8)+
        paper('docx',777,104,165,211,'#e6f2d6',spec.ink,'DOCX','RESEARCH',18);
      paths = 'M233 306 L540 360 L429 292 M660 295 L540 360 L856 306';
      marks = '<g transform="translate(550 333)"><g data-ft-core-wrap><path data-ft-core class="ft-core" d="'+spec.shapes[2]+'" transform="scale(.38)"/><g data-ft-core-detail><path d="M-19-7 H19 M-19 5 H19" stroke="#164d41" stroke-width="2"/></g></g></g>';
    }
    return `<svg class="ft-svg" viewBox="0 0 1080 470" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
      <path class="ft-grid" d="M33 38 H1047 M33 427 H1047 M58 22 V440 M1022 22 V440 M30 70 H85 M58 42 V98 M995 392 H1045 M1022 366 V421"/>
      <text x="65" y="207" class="ft-word">${spec.word}</text>
      <g data-ft-parallax="back"><g data-ft-camera><path data-ft-connect class="ft-connect" d="${paths}"/>
      ${objects}<g data-ft-parallax="front">${marks}</g>
      <g data-ft-traveller><path d="M-13-6 H13 V6 H-13 Z" fill="${spec.light}" stroke="${spec.ink}" stroke-width="1.2"/></g>
      <g data-ft-traveller-secondary><path d="M-8-5 H8 V5 H-8 Z" fill="${spec.accent}" stroke="${spec.ink}" stroke-width="1.2"/></g>
      </g></g>
      <g data-ft-foreground aria-hidden="true"><path d="M-370-430 H-70 V270 H-370 Z" fill="${spec.accent}"/><path d="M-330-370 H-110 M-330-345 H-160" stroke="${spec.ink}" stroke-width="2" opacity=".3"/></g>
    </svg>`;
  }
  const PROFILES = {
    qa:{name:'question-weave',cycle:12.8,scroll:28},
    scope:{name:'precision-rails',cycle:15.4,scroll:15},
    counter:{name:'evidence-peel',cycle:14.6,scroll:24},
    replay:{name:'archive-depth',cycle:18.2,scroll:36},
    assets:{name:'spatial-index',cycle:16.4,scroll:24}
  };
  let artworkSerial=0;
  // The report that crosses the native route becomes these real scene outlines.
  // Coordinates are authored product geometry, never financial observations.
  const REPORT_ANCHORS={qa:[420,84,208,282],scope:[420,82,218,292],counter:[480,95,210,280],replay:[440,84,228,302],assets:[425,91,211,283]};
  const rectPath=(x,y,w,h)=>`M${x} ${y} H${x+w} V${y+h} H${x} Z`;
  function reportFoldArtwork(scene,spec,id){
    const [ax,ay,aw,ah]=REPORT_ANCHORS[scene],w=Math.min(aw,ah/1.31)*.96,h=w*1.31,x=ax+(aw-w)/2,y=ay+(ah-h)/2;
    const folder=(fx,fy)=>`M${fx} ${fy} H${fx+61} L${fx+77} ${fy+15} H${fx+172} V${fy+116} H${fx} Z`;
    const archive=(fx,fy,fw,fh)=>`M${fx} ${fy} L${fx+fw} ${fy-fw*.19438} V${fy+fh-fw*.19438} L${fx} ${fy+fh} Z`;
    const definitions={
      qa:[[rectPath(125,86,177,66),'#255be8'],[rectPath(113,177,177,66),'#e4ee88'],[rectPath(134,268,177,66),'#255be8'],['M448 137 H593 V296 L560 329 V296 H448 Z','#153c91'],[rectPath(680,79,268,81),'#f6f8ef'],[rectPath(680,181,268,116),'#d8e5fb'],[rectPath(680,318,268,67),'#e4ee88']],
      scope:Array.from({length:6},(_,i)=>[rectPath(146,68+i*53,768,42),i%2?'#344bb4':'#4b60be']),
      counter:[['M160 69 H412 V329 L335 397 H160 Z','#ed7b60'],[rectPath(360,91,343,311),'#fff0d5'],['M780 150 A86 86 0 1 1 780 322 A86 86 0 1 1 780 150 Z','#4c293f'],['M828 303 L840 291 L909 359 L897 371 Z','#4c293f']],
      replay:[[archive(709,46,215,269),'#bfa5d9'],[archive(441,83,250,298),'#e4d5f3'],[archive(148,132,282,294),'#faf4ff']],
      assets:[[folder(130,104),'#dbe5a7'],[folder(394,58),'#9fd6b4'],[folder(750,94),'#f2f0d4'],[folder(631,277),'#b3d969']]
    };
    const panels=definitions[scene],strip=h/panels.length;
    const art=panels.map(([shape,color],i)=>{
      const sy=y+i*strip,direction=i%2?1:-1,shift=direction*(36+i*3),fold=strip*.32;
      const middle=`M${x+shift} ${sy+fold} L${x+w+shift} ${sy-fold} L${x+w-shift*.2} ${sy+strip-fold} L${x-shift*.2} ${sy+strip+fold} Z`;
      return `<path data-ft-fold-panel="${i}" data-ft-fold-middle="${middle}" data-ft-fold-target="${shape}" data-ft-fold-color="${color}" d="${rectPath(x,sy,w,strip+.25)}" fill="#f1efdf" stroke="#c6c8b8" stroke-width=".5"${scene==='counter'&&i===2?` mask="url(#${id}-fold-aperture)"`:''}/>`;
    }).join('');
    return `<defs><mask id="${id}-fold-aperture" maskUnits="userSpaceOnUse" x="75" y="20" width="950" height="420"><rect x="75" y="20" width="950" height="420" fill="#fff"/><circle data-ft-fold-aperture cx="780" cy="236" r="0" fill="#000"/></mask></defs><g data-ft-handoff-paper data-ft-handoff-kind="${scene}" opacity="0" pointer-events="none">${art}<g data-ft-fold-print><path d="M${x+1} ${y} h${w*.06} v${h} h${-w*.06}Z" fill="${spec.ink}"/><text x="${x+w*.14}" y="${y+h*.12}" fill="${spec.ink}" font-size="8" letter-spacing=".8">QINGMENG / RESEARCH</text><text x="${x+w*.14}" y="${y+h*.34}" fill="#132921" font-size="25" font-weight="800">${spec.name}</text><path d="M${x+w*.14} ${y+h*.57} h${w*.68} M${x+w*.14} ${y+h*.65} h${w*.5} M${x+w*.14} ${y+h*.73} h${w*.6}" stroke="#203e42" stroke-opacity=".3" stroke-width="1"/><path d="M${x+w*.84} ${y} v${w*.16} h${w*.16} Z" fill="#c8cbbb"/></g></g>`;
  }
  // Authored final poses are complete without JavaScript. Each scene has its own
  // geometry and motion vocabulary; the legacy optional dialog is kept separate.
  function inlineArtwork(scene,spec) {
    const id='qm-art-'+(++artworkSerial);
    const layer=(name,x,y,content,extra='')=>`<g transform="translate(${x} ${y})"><g data-ft-arrive="${name}"><g data-ft-response="${name}"><g data-ft-float="${name}" data-ft-float-kind="${name}" ${extra}>${content}</g></g></g></g>`;
    const linework=(x,y,width,count=5,color=spec.ink)=>Array.from({length:count},(_,i)=>`<path d="M${x} ${y+i*23} h${width-(i%3)*27}" fill="none" stroke="${color}" stroke-width="${i===0?4:2}" opacity="${i===0?.65:.28}"/>`).join('');
    const sheet=(width,height,fill,ink,title,kicker)=>`<path d="M9 11 H${width+9} V${height+11} H9 Z" fill="${ink}" opacity=".09"/><path d="M4 5 H${width+4} V${height+5} H4 Z" fill="${ink}" opacity=".22"/><rect width="${width}" height="${height}" fill="${fill}" stroke="${ink}" stroke-opacity=".25"/><path d="M1 1 H${width-1}" stroke="#fff" stroke-opacity=".8"/><text x="23" y="35" class="ft-art-kicker" fill="${ink}">${kicker}</text><text x="23" y="83" class="ft-art-title" fill="${ink}">${title}</text>${linework(23,119,width-48,Math.max(2,Math.floor((height-130)/23)),ink)}`;
    let body='';
    if(scene==='qa') {
      const words=['企业','期间','指标'];
      body=`<g data-ft-parallax="back"><g data-ft-camera>
        <path data-ft-qa-thread d="M209 138 C410 102 362 219 521 226 S698 141 874 192 M212 219 C395 257 367 128 521 226 S692 307 874 280 M225 307 C407 345 402 271 521 226 S730 369 876 363" fill="none" stroke="#255be8" stroke-width="2.2" opacity=".46"/>
        <path d="M527 68 V401" stroke="#153c91" stroke-width="1" stroke-dasharray="3 11" opacity=".16"/>
        ${words.map((word,i)=>layer('keyword-'+i,113+[12,0,21][i],86+i*91,`<rect x="5" y="7" width="177" height="66" fill="#163fb7" opacity=".12"/><rect width="177" height="66" fill="${i===1?'#e4ee88':'#255be8'}"/><text x="22" y="42" class="ft-art-title" fill="${i===1?'#153c91':'#f5f8ff'}">${word}</text><path d="M133 25 l9 9 -9 9" stroke="${i===1?'#153c91':'#e4ee88'}" stroke-width="2" fill="none"/>`,i===0?'data-ft-ambient-witness':'')).join('')}
        ${layer('question-junction',448,137,`<path d="M0 0 H145 V159 L112 192 V159 H0 Z" fill="#153c91"/><path d="M13 14 H131" stroke="#f5f8ff" opacity=".4"/><text x="70" y="112" text-anchor="middle" font-size="94" font-weight="650" fill="#e4ee88">?</text><path d="M28 144 H116" stroke="#e4ee88" stroke-width="2"/>`)}
        <g data-ft-parallax="front">${layer('answer-structure',680,79,`<g data-ft-answer-block="0"><path d="M7 10 H275 V91 H7 Z" fill="#153c91" opacity=".12"/><rect width="268" height="81" fill="#f6f8ef" stroke="#153c91" stroke-opacity=".35"/><text x="23" y="31" class="ft-art-kicker" fill="#153c91">ANSWER / 有据的回答</text><text x="23" y="62" class="ft-art-title" fill="#153c91">结论</text><path d="M189 55 H244" stroke="#255be8" stroke-width="6"/></g><g data-ft-answer-block="1"><rect y="102" width="268" height="116" fill="#d8e5fb" stroke="#153c91" stroke-opacity=".25"/><text x="23" y="139" class="ft-art-copy" fill="#153c91">数值 · 计算</text>${linework(23,162,196,2,'#153c91')}</g><g data-ft-answer-block="2"><rect y="239" width="268" height="67" fill="#e4ee88"/><text x="23" y="279" class="ft-art-copy" fill="#153c91">原文 · 来源</text><path d="M224 273 h20 m-8-8 8 8 -8 8" stroke="#153c91" stroke-width="2" fill="none"/></g>`)}</g>
        <g data-ft-pulse><circle r="6" fill="#e4ee88" stroke="#153c91" stroke-width="2"/></g>
      </g></g>`;
    } else if(scene==='scope') {
      const names=['指标定义','单位币种','报告期间','合并范围','会计政策','披露版本'];
      body=`<g data-ft-parallax="back"><g data-ft-camera><path d="M132 49 H963 M132 405 H963" stroke="#cbd8ff" stroke-opacity=".25"/><text x="130" y="34" class="ft-art-kicker" fill="#cbd8ff">COMPARABILITY / 对齐研究前提</text>
        ${names.map((name,i)=>layer('rail-'+i,146,68+i*53,`<g data-ft-ruler="${i}"><rect width="768" height="42" fill="${i%2?'#344bb4':'#4b60be'}"/><rect width="7" height="42" fill="#dfeb7a"/><text x="22" y="29" class="ft-art-kicker" fill="#d8e3ff">0${i+1}</text><text x="76" y="29" class="ft-art-copy" fill="#f3f5ff">${name}</text>${Array.from({length:24},(_,j)=>`<path d="M${263+j*20} ${j%4===0?9:19} v${j%4===0?22:12}" stroke="#d8e3ff" opacity="${j%4===0?.67:.32}"/>`).join('')}<rect x="731" y="15" width="12" height="12" fill="#dfeb7a" opacity=".9"/></g>`,i===0?'data-ft-ambient-witness':'')).join('')}
        <g data-ft-parallax="front"><g data-ft-scope-guide><path d="M568 48 V405" stroke="#dfeb7a" stroke-width="2"/><path d="M558 48 H579 M558 405 H579" stroke="#dfeb7a" stroke-width="4"/><rect x="545" y="211" width="47" height="47" fill="none" stroke="#f3f5ff" stroke-width="2"/></g><g data-ft-scope-measure><rect x="875" y="180" width="97" height="105" fill="#dfeb7a"/><path d="M895 207 h56 M895 230 h56 M895 253 h56" stroke="#213899" stroke-width="2"/><path d="M923 194 V268" stroke="#213899" stroke-width="2"/></g></g>
        <text x="146" y="432" class="ft-art-kicker" fill="#e3ebff">相同参照下，让差异显现。</text></g></g>`;
    } else if(scene==='counter') {
      body=`<defs><linearGradient id="${id}-paper" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff9e9"/><stop offset="1" stop-color="#e7c9b2"/></linearGradient><linearGradient id="${id}-fold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ffd5a9"/><stop offset=".66" stop-color="#fff0d2"/><stop offset="1" stop-color="#a14e49"/></linearGradient><clipPath id="${id}-source"><rect x="360" y="91" width="343" height="311"/></clipPath><clipPath id="${id}-lens"><circle r="77"/></clipPath></defs>
        <g data-ft-parallax="back"><g data-ft-camera>
        <path d="M278 140 731 70 815 385 355 439Z" fill="#4c293f" opacity=".045"/><path d="M326 103 722 79 744 407 349 431Z" fill="#4c293f" opacity=".075"/>
        <g clip-path="url(#${id}-source)"><g data-ft-source-paper><path d="M368 102 H708 V416 H368Z" fill="#4c293f" opacity=".17"/><rect x="360" y="91" width="343" height="311" fill="url(#${id}-paper)"/><path d="M361 92 H702" stroke="#fff"/><text x="389" y="126" class="ft-art-kicker" fill="#764d54">ORIGINAL / 追索依据</text><text x="389" y="169" class="ft-art-title" fill="#4c293f">原文与计算</text>${linework(389,207,271,7,'#4c293f')}<path d="M389 245 H648" stroke="#ef795d" stroke-width="21" opacity=".28"/><path d="M389 245 H617" stroke="#4c293f" stroke-width="2"/></g></g>
        ${layer('claim-peel',160,69,`<g data-ft-peel><path d="M9 12 H260 V340 H9Z" fill="#4c293f" opacity=".15"/><path d="M3 4 H254 V332 H3Z" fill="#a44f4c"/><path d="M0 0 H252 V260 L175 328 H0 Z" fill="#ed7b60"/><path d="M2 1 H250" stroke="#ffcbbb"/><text x="25" y="38" class="ft-art-kicker" fill="#542b3b">CANDIDATE</text><text x="25" y="96" class="ft-art-title" fill="#4c293f">候选答案</text><text x="24" y="179" font-size="84" font-weight="750" fill="#fff0d5">WHY?</text>${linework(25,218,194,2,'#4c293f')}<path data-ft-fold d="M175 328 L177 260 L252 260 Z" fill="url(#${id}-fold)" stroke="#965653" stroke-opacity=".2"/></g>`,'data-ft-ambient-witness')}
        <g data-ft-parallax="front">${layer('source-lens',780,236,`<g data-ft-lens><path d="M56 61 122 126" stroke="#4c293f" stroke-width="17"/><path d="M57 58 123 123" stroke="#bd6259" stroke-width="5"/><circle cy="7" r="87" fill="#4c293f" opacity=".11"/><circle r="86" fill="#fff5df" stroke="#4c293f" stroke-width="3"/><g clip-path="url(#${id}-lens)"><rect x="-90" y="-85" width="180" height="170" fill="#fff5df"/><g data-ft-source-detail><path d="M-96-24 H99 M-99 21 H100 M-100 59 H91" stroke="#4c293f" stroke-width="5"/><path d="M-102-24 H57" stroke="#ef795d" stroke-width="27" opacity=".33"/><path d="M-94-58 H49" stroke="#b67b70" stroke-width="3"/><path d="M-97-24 H68" stroke="#4c293f" stroke-width="5"/></g></g><circle r="79" fill="none" stroke="#dcae93" stroke-width="1"/><path d="M-57-46 A72 72 0 0 1 38-62" stroke="#fff" stroke-width="5" fill="none" opacity=".7"/></g>`)}</g>
        <path data-ft-counter-link d="M416 245 H697" stroke="#4c293f" stroke-dasharray="3 7" opacity=".35"/><text x="694" y="400" class="ft-art-kicker" fill="#764d54">向原文，再看一层。</text></g></g>`;
    } else if(scene==='replay') {
      body=`<defs><linearGradient id="${id}-light" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#fff9ff" stop-opacity="0"/><stop offset=".48" stop-color="#fff9ff" stop-opacity=".33"/><stop offset="1" stop-color="#fff9ff" stop-opacity="0"/></linearGradient></defs>
        <g data-ft-parallax="back"><g data-ft-camera><path d="M122 390 779 89 981 327 322 448Z" fill="#4b2a71" opacity=".045"/><path d="M187 402 801 145 M337 434 938 225" stroke="#4b2a71" stroke-opacity=".17"/><g data-ft-archive-depth><path d="M134 358 824 55 M349 437 1011 141" stroke="#4b2a71" stroke-opacity=".12" stroke-dasharray="3 9"/></g>
        ${layer('archive-back',709,46,`<g data-ft-archive-layer="2" transform="skewY(-11)">${sheet(215,269,'#bfa5d9','#4b2a71','核验记录','03 / RECHECK')}<path d="M215 0 l13 9 v269 l-13-9Z" fill="#805d9f"/><rect x="23" y="231" width="169" height="17" fill="#4b2a71" opacity=".12"/></g>`)}
        ${layer('archive-middle',441,83,`<g data-ft-archive-layer="1" transform="skewY(-11)">${sheet(250,298,'#e4d5f3','#4b2a71','来源档案','02 / SOURCES')}<path d="M250 0 l15 10 v298 l-15-10Z" fill="#9676af"/><rect x="23" y="249" width="192" height="22" fill="#a682df" opacity=".48"/></g>`)}
        <g data-ft-parallax="front">${layer('archive-front',148,132,`<g data-ft-archive-layer="0" transform="skewY(-11)">${sheet(282,294,'#faf4ff','#4b2a71','条件快照','01 / CONTEXT')}<path d="M282 0 l16 10 v294 l-16-10Z" fill="#b296c9"/><path d="M0 294 H282 l16 10 H16 Z" fill="#cbb6dc"/><rect x="23" y="244" width="88" height="25" fill="#4b2a71"/><text x="33" y="262" font-size="13" fill="#faf4ff">FROZEN</text><path d="M149 259 H251" stroke="#b899e9" stroke-width="4"/></g>`,'data-ft-ambient-witness')}</g>
        <g data-ft-archive-light pointer-events="none"><path d="M261 30 383 18 788 415 638 440Z" fill="url(#${id}-light)"/></g>
        <text x="649" y="422" class="ft-art-kicker" fill="#694481">沿着发生顺序，重新建立联系。</text></g></g>`;
    } else {
      const nodes=[['csv','CSV','结构化',130,104,'#dbe5a7'],['xlsx','XLSX','工作簿',394,58,'#9fd6b4'],['pdf','PDF','原始披露',750,94,'#f2f0d4'],['docx','DOCX','研究文档',631,277,'#b3d969']];
      body=`<g data-ft-parallax="back"><g data-ft-camera><path d="M121 357 563 107 973 302 532 447Z" fill="#123f35" stroke="#e4f4dd" stroke-opacity=".12"/><path d="M233 405 671 156 M346 459 788 210 M123 357 532 447 M342 232 752 423 M563 107 973 302" stroke="#e4f4dd" stroke-opacity=".09"/>
        <g data-ft-index-network>${nodes.map((n,i)=>`<path data-ft-index-link="${n[0]}" d="${['M231 197 L490 263','M479 173 L518 253','M822 202 L576 268','M704 323 L570 284'][i]}" fill="none" stroke="#c4e58e" stroke-width="2" opacity=".5"/>`).join('')}</g>
        <g transform="translate(525 277)"><g data-ft-index-hub><path d="M0-44 79-6 0 36-79-6Z" fill="#c4e58e"/><path d="M-79-6 0 36 79-6 V12 L0 55-79 12Z" fill="#78a65f"/><path d="M0-24 42-5 0 17-42-5Z" fill="none" stroke="#164d41" stroke-width="2"/><path d="M0 17 V36" stroke="#164d41" opacity=".3"/></g></g>
        ${nodes.map((n,i)=>layer('asset-'+n[0],n[3],n[4],`<g data-ft-index-item="${n[0]}"><g data-ft-index-hover="${n[0]}"><path d="M8 9 H179 V125 H8Z" fill="#091f18" opacity=".3"/><path d="M0 0 H61 L77 15 H172 V116 H0Z" fill="${n[5]}"/><path d="M1 1 H60 L76 16 H171" stroke="#f2f9e9" opacity=".65"/><text x="20" y="55" class="ft-art-title" fill="#164d41">${n[1]}</text><text x="20" y="92" class="ft-art-copy" fill="#164d41">${n[2]}</text><path d="M128 86 h21 m-7-7 7 7 -7 7" fill="none" stroke="#164d41" stroke-width="2"/></g></g>`,i===0?'data-ft-ambient-witness':'')).join('')}
        <g data-ft-parallax="front"><g transform="translate(182 379)"><g data-ft-index-label><path d="M0 0 H252 V48 H0Z" fill="#e4f4dd"/><text x="17" y="31" class="ft-art-copy" fill="#164d41">来源 · 版本 · 研究用途</text></g></g></g>
        <g data-ft-index-pulse><circle r="5" fill="#e4f4dd"/></g></g></g>`;
    }
    const [x,y,w,h]=REPORT_ANCHORS[scene];
    // Each edition opens through its own geometric aperture. The complete
    // static aperture is authored first, so a missing engine never hides art.
    const aperture=scene==='counter'?'<circle data-ft-aperture cx="550" cy="230" r="900"/>':'<rect data-ft-aperture x="-75" y="-130" width="1250" height="720"/>';
    return `<svg class="ft-svg" data-ft-composition="${PROFILES[scene].name}" viewBox="75 20 950 420" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg"><defs><clipPath id="${id}-edition" clipPathUnits="userSpaceOnUse">${aperture}</clipPath></defs><rect data-qm-route-report-target x="${x}" y="${y}" width="${w}" height="${h}" fill="none" opacity="0" pointer-events="none"/><g clip-path="url(#${id}-edition)"><g data-ft-handoff-art>${body}</g></g>${reportFoldArtwork(scene,spec,id)}</svg>`;
  }
  let current = null, disposed = false, inlineRoute = '';
  const inlineRecords = new Map(), inlineSnapshots = new Map(), inlineContexts = new Map();
  const DIMENSIONS=['definition','currency_unit','period','consolidation_scope','accounting_policy','restatement_version'];
  const CATEGORIES={qa:['data','source','explanation','verification','query','export','analysis'],scope:['six','probe','dimensions','sources','manual'],counter:['checks','source','review'],replay:['generate','import','answer','query','source','check'],assets:['overview','import','library','evaluation','review']};
  const ASSETS=['upload','disclosure','sources','catalog','public'];
  const TYPES=['pdf','csv','xlsx','xls','docx','json','zip','all','other','tabular','builtin'];
  function contextState(scene,value){
    if(!SPECS[scene] || !value || value.v!==1 || Array.isArray(value))return null;
    const token=item=>item===null || item===undefined || (typeof item==='string' && /^[a-f0-9]{16}$/.test(item));
    const choice=(item,allowed)=>item===null || item===undefined || allowed.includes(item);
    if(!token(value.company) || !(token(value.source) || (Number.isSafeInteger(value.source) && value.source>=0)) ||
      !choice(value.dimension,DIMENSIONS) || !choice(value.category,CATEGORIES[scene]) || !choice(value.asset,ASSETS) || !choice(value.type,TYPES))return null;
    return {v:1,company:value.company??null,dimension:value.dimension??null,source:value.source??null,category:value.category??null,asset:value.asset??null,type:value.type??null};
  }
  // These poses express selection and reading priority, never a financial
  // result. Only decorative wrappers receive transforms; native controls stay put.
  function responsePose(scene,name,state){
    const pose={x:0,y:0,scale:1,rotation:0,opacity:1};
    const sourceSeed=typeof state.source==='number'?state.source:state.source?parseInt(state.source.slice(-6),16):0;
    const sourceOffset=(sourceSeed%7-3)*5;
    if(state.company && /keyword|claim|archive|asset/.test(name)){
      const seed=parseInt(state.company.slice(0,4),16),index=Number(name.slice(-1))||name.length;
      pose.x=((seed+index*7)%5-2)*7;pose.y=((seed+index*3)%3-1)*6;
    }
    if(scene==='scope' && state.dimension){
      const selected=name==='rail-'+DIMENSIONS.indexOf(state.dimension);
      Object.assign(pose,{x:selected?38:-26,scale:selected?1.03:1,opacity:selected?1:.36});
    }else if(scene==='qa' && (state.source!==null || ['source','explanation'].includes(state.category))){
      if(name==='answer-structure')Object.assign(pose,{x:-68+sourceOffset,y:-9+(sourceSeed%3-1)*6,scale:1.12});
      else if(name==='question-junction')Object.assign(pose,{x:-40,scale:.88,opacity:.65});
      else pose.opacity=.55;
    }else if(scene==='counter' && (state.source!==null || state.category==='source')){
      if(name==='claim-peel')Object.assign(pose,{x:-63,y:14,rotation:-6,opacity:.55});
      if(name==='source-lens')Object.assign(pose,{x:-84+sourceOffset,y:-20+(sourceSeed%3-1)*8,rotation:(sourceSeed%5-2)*2,scale:1.16});
    }else if(scene==='replay' && ['answer','query','source','check'].includes(state.category)){
      const target=state.category==='source'?'archive-middle':state.category==='check'?'archive-back':'archive-front';
      const chosen=name===target;
      Object.assign(pose,{x:chosen?(name==='archive-back'?-128:name==='archive-front'?58:-18):name==='archive-front'?-42:44,y:chosen?-18:18,scale:chosen?1.1:.94,opacity:chosen?1:.42});
    }else if(scene==='assets'){
      const type=state.type==='xls'?'xlsx':state.type==='tabular'?'csv':state.type;
      const target=['csv','xlsx','pdf','docx'].includes(type)?'asset-'+type:['disclosure','public'].includes(state.asset)?'asset-pdf':null;
      if(target){const chosen=name===target;Object.assign(pose,{y:chosen?-26:20,scale:chosen?1.16:.92,opacity:chosen?1:.4});}
      else if(state.asset==='upload' || state.category==='import')Object.assign(pose,{y:-20,x:name==='asset-csv'?-32:32,rotation:name==='asset-csv'?-4:4});
    }
    return pose;
  }
  function settleResponse(record){
    if(!record.response)return;
    for(const item of record.response){
      Object.values(item.quick).forEach(fn=>fn.tween.pause());
      if(item.pose)win.gsap.set(item.node,item.pose);
    }
  }
  function applyContext(record,entry,animate=false){
    record.contextRevision=entry.revision;
    if(!record.response)return;
    for(const item of record.response){
      item.pose=responsePose(record.scene,item.name,entry.state);
      if(animate && canPlay(record) && !record.paused && record.arrived && !record.handoff){
        for(const [key,value] of Object.entries(item.pose)){
          if(key==='scale'){item.quick.scaleX(value);item.quick.scaleY(value);}
          else item.quick[key](value);
        }
      }else{
        Object.values(item.quick).forEach(fn=>fn.tween.pause());
        win.gsap.set(item.node,item.pose);
      }
    }
  }
  function setContext(scene,value){
    const state=contextState(scene,value);
    if(!state || ![...inlineRecords.values()].some(record=>record.scene===scene))return false;
    const key=JSON.stringify(state),prior=inlineContexts.get(scene);
    if(prior?.key===key)return false;
    const entry={state,key,revision:(prior?.revision||0)+1};inlineContexts.set(scene,entry);
    for(const record of inlineRecords.values())if(record.scene===scene)applyContext(record,entry,Boolean(prior));
    return true;
  }
  const live = record => current === record || inlineRecords.get(record.host) === record;
  const records = () => [...inlineRecords.values(), ...(current ? [current] : [])];
  const canPlay = record => !record.static && !record.held && record.visible !== false && !doc.hidden && record.node.isConnected && (!record.inline || !current);
  function notify(open) { win.dispatchEvent(new win.CustomEvent('qm-feature-theater-change', {detail:{open}})); }
  function notifyInline() { win.dispatchEvent(new win.CustomEvent('qm-feature-inline-change',{detail:{mounted:inlineRecords.size}})); }
  function markup(scene, spec, inline = false) {
    // The page artwork is a living part of its layout, never a media player.
    // A separate HTML wrapper gives scroll depth its own transform owner.
    if (inline) return `<div class="ft-stage"><div class="ft-scroll-layer" data-ft-scroll>${inlineArtwork(scene,spec)}</div></div>`;
    const result = `<header class="ft-top"><div><div class="ft-eyebrow"><span>擎梦数智 / MOTION STUDY ${spec.number}</span><span>功能概念演示</span></div><h2 class="ft-title" id="qm-ft-title">${spec.title}</h2></div><button type="button" class="ft-close" data-ft-close aria-label="关闭演示舞台" title="关闭（Esc）">×</button></header>
      <div class="ft-stage">${artwork(scene,spec)}<div class="ft-stage-meta"><span>${spec.name} / EVIDENCE IN MOTION</span><span>移动鼠标，探索前后层次</span></div><div class="ft-vignette"></div></div>
      <footer class="ft-bottom"><nav class="ft-chapters" aria-label="演示章节">${spec.chapters.map((name,i)=>`<button type="button" data-ft-chapter="${i}"${i===0?' aria-current="step"':''}><small>0${i+1} / CHAPTER</small><strong>${name}</strong></button>`).join('')}</nav><div class="ft-controls"><p class="ft-caption" id="qm-ft-description">${spec.descriptions[0]}</p><div class="ft-scrub-wrap"><input class="ft-scrub" data-ft-scrub type="range" min="0" max="1000" step="1" value="0" aria-label="概念演示播放位置" aria-valuetext="第 1 幕"><output data-ft-time>0:00</output></div><div class="ft-playback"><button class="ft-pause" type="button" data-ft-pause>暂停</button><button type="button" data-ft-replay>重播</button></div></div><p class="ft-footnote"><span>功能概念示意 · 不表示实时分析进度、财务数据或核验结果。</span><span class="ft-status" data-ft-status aria-live="polite">准备演示</span></p></footer>`;
    return result;
  }
  function syncControls(record) {
    if (!live(record)) return;
    if (record.inline) return;
    const seconds = record.timeline?.time() ?? (record.static ? 11.1 : 0);
    const index = seconds >= 7.8 ? 2 : seconds >= 3.5 ? 1 : 0;
    if (record.chapter !== index) {
      record.chapter = index;
      record.caption.textContent = record.spec.descriptions[index];
      record.chapters.forEach((button,i) => i === index ? button.setAttribute('aria-current','step') : button.removeAttribute('aria-current'));
      record.scrub.setAttribute('aria-valuetext', '第 ' + (index+1) + ' 幕：' + record.spec.chapters[index]);
    }
    const rounded = Math.floor(seconds);
    if (record.second !== rounded) { record.second = rounded; record.time.textContent = '0:' + String(rounded).padStart(2,'0'); }
    record.scrub.value = String(Math.round((record.timeline?.progress() ?? (record.static ? 1 : 0)) * 1000));
  }
  function setState(record) {
    if (!live(record)) return;
    if (record.inline) return;
    const state = record.static ? '静态展示' : record.held ? '等待呈现' : doc.hidden ? '后台暂停' : record.visible === false ? '离屏暂停' : record.ended ? '演示结束' : record.paused ? '已暂停' : '演示播放中';
    if (record.status.textContent !== state) record.status.textContent = state;
    record.pause.textContent = record.ended ? '再播放' : record.paused ? '继续' : '暂停';
    record.pause.disabled = record.static || record.held;
    record.replay.disabled = record.static || record.held;
    record.scrub.disabled = record.static || record.held;
    record.chapters.forEach(button => { button.disabled = record.static || record.held; });
  }
  function applyPlayback(record) {
    if (!live(record)) return;
    if (record.inline) {
      record.syncReading?.();
      const active = canPlay(record) && !record.paused;
      if (active) {
        if(record.handoff){record.timeline?.pause();record.ambient?.pause();record.handoff.play();}
        else if (record.arrived) record.ambient?.play();
        else record.timeline?.play();
      } else {
        if(record.handoff)finishHandoff(record);
        record.timeline?.pause();
        record.ambient?.pause();
        settleResponse(record);
        record.quick?.forEach(({x,y})=>{x.tween.pause();y.tween.pause();});
      }
      const scrollActive=active&&!record.handoff;
      if (record.scrollTrigger && record.scrollEnabled !== scrollActive) {
        record.scrollEnabled = scrollActive;
        if (scrollActive) record.scrollTrigger.enable(false, true);
        else {record.scrollTrigger.disable(false);record.scrollTrigger.getTween?.()?.pause();}
      }
      return;
    }
    if (canPlay(record) && !record.paused) record.timeline?.play();
    else {
      record.timeline?.pause();
      record.quick?.forEach(({x,y})=>{x.tween.pause();y.tween.pause();});
    }
    setState(record);
  }
  function finishHandoff(record){
    record.handoff?.kill();record.handoff=null;record.handoffProgress=1;
    const gsap=win.gsap;
    if(!gsap)return;
    const paper=record.node.querySelector('[data-ft-handoff-paper]'),art=record.node.querySelector('[data-ft-handoff-art]');
    if(paper)gsap.set(paper,{opacity:0});if(art)gsap.set(art,{opacity:1});
  }
  function startHandoff(record){
    const gsap=win.gsap;
    if(record.handoffDone || !canPlay(record) || quiet() || !gsap?.timeline || !win.MorphSVGPlugin)return false;
    const paper=record.node.querySelector('[data-ft-handoff-paper]'),art=record.node.querySelector('[data-ft-handoff-art]');
    const panels=[...record.node.querySelectorAll('[data-ft-fold-panel]')];
    if(!paper || !art || !panels.length)return false;
    record.handoffDone=true;record.handoffProgress=0;
    // The .12 camera and real business response are already in their final
    // pose. A separate, bounded fold owns only this temporary paper drawing.
    record.context.add(()=>{
      gsap.set(art,{opacity:0});gsap.set(paper,{opacity:1});
      const tl=gsap.timeline({id:'qm-feature-handoff-'+record.scene,paused:true,defaults:{ease:'power2.inOut'},
        onUpdate:()=>{record.handoffProgress=tl.progress();},onComplete:()=>{if(live(record)){finishHandoff(record);applyPlayback(record);}}});
      record.handoff=tl;
      tl.to(record.node.querySelector('[data-ft-fold-print]'),{opacity:0,duration:.18,ease:'power1.out'},.06);
      panels.forEach((panel,i)=>{
        const offset=i*.024;
        tl.to(panel,{morphSVG:{shape:panel.getAttribute('data-ft-fold-middle'),shapeIndex:0},duration:.30,fill:i%2?'#d8dacb':'#fffaf0'},.08+offset);
        tl.to(panel,{morphSVG:{shape:panel.getAttribute('data-ft-fold-target'),shapeIndex:0},fill:panel.getAttribute('data-ft-fold-color'),stroke:record.spec.ink,strokeOpacity:.18,duration:.66},.38+offset);
        tl.to(panel,{opacity:0,duration:.24,ease:'power1.in'},.96+offset);
      });
      if(record.scene==='counter')tl.to(record.node.querySelector('[data-ft-fold-aperture]'),{attr:{r:77},duration:.58},.48);
      tl.to(art,{opacity:1,duration:.46,ease:'power2.out'},.70);
    });
    applyPlayback(record);return true;
  }
  function clearReadingContext(record){
    record.readingTrigger?.kill();record.readingTrigger=null;
    record.readingStrip?.remove();record.readingStrip=null;
    record.syncReading=null;record.refreshReading=null;
  }
  function setupReadingContext(record){
    const spread=record.host.closest('[data-feature-spread]');
    if(!spread || !win.ScrollTrigger?.create || !doc.body)return;
    const heading=spread.querySelector('.feature-title-mask h2');
    if(!heading)return;
    const scroller=record.host.closest('[data-testid="stMain"]')||win;
    const strip=doc.createElement('aside'),copy=doc.createElement('div'),title=doc.createElement('strong'),detail=doc.createElement('span');
    strip.className='feature-reading-strip';strip.hidden=true;
    strip.setAttribute('data-qm-feature-reading',record.scene);strip.setAttribute('aria-label','当前研究');
    copy.className='feature-reading-copy';copy.append(title,detail);strip.append(copy);doc.body.append(strip);
    record.readingStrip=strip;record.readingPast=false;record.readingWide=false;
    record.syncReading=()=>{strip.hidden=!(record.readingPast&&record.readingWide&&!record.held&&!doc.hidden&&!current&&live(record));};
    record.refreshReading=()=>{
      const bounds=spread.getBoundingClientRect(),viewport=scroller===win?{top:0}:scroller.getBoundingClientRect();
      const text=[...spread.querySelectorAll('[data-feature-work-context]')].map(node=>node.textContent.trim()).filter(Boolean).join(' · ');
      if(title.textContent!==heading.textContent)title.textContent=heading.textContent;
      if(detail.textContent!==text)detail.textContent=text;
      detail.hidden=!text;
      const source=spread.querySelector('[data-feature-work-link]'),href=source?.getAttribute('href');
      let link=strip.querySelector('a');
      if(source&&/^#[A-Za-z][A-Za-z0-9_-]*$/.test(href||'')){
        if(!link){link=doc.createElement('a');strip.append(link);}
        if(link.getAttribute('href')!==href)link.setAttribute('href',href);
        const label=source.querySelector('span')?.textContent||source.textContent;
        if(link.textContent!==label+' ↘')link.textContent=label+' ↘';
      }else link?.remove();
      record.readingWide=(win.innerWidth||0)>=1000&&bounds.width>0;
      strip.style.left=Math.max(8,bounds.left)+'px';strip.style.width=Math.max(0,bounds.width)+'px';
      strip.style.top=Math.max(12,viewport.top+12)+'px';
      strip.style.setProperty('--reading-accent',record.spec.ink);
      record.syncReading();
    };
    const update=self=>{record.readingPast=self.scroll()>=self.start;record.syncReading();};
    // This trigger only switches read-only context. It never owns a transform,
    // pins content, replays art or depends on the motion preference.
    record.readingTrigger=win.ScrollTrigger.create({trigger:spread,scroller,start:'bottom top+=72',end:'max',pin:false,markers:false,
      onUpdate:update,onRefresh:self=>{record.refreshReading();update(self);}});
    record.refreshReading();update(record.readingTrigger);
  }
  function setupInlineMotion(record) {
    const gsap=win.gsap,profile=PROFILES[record.scene];
    record.static=quiet() || !gsap?.timeline;
    if(!gsap?.timeline) {record.paused=true;record.ended=true;record.arrived=true;return;}
    if(win.MorphSVGPlugin)gsap.registerPlugin(win.MorphSVGPlugin);
    if(win.MotionPathPlugin)gsap.registerPlugin(win.MotionPathPlugin);
    if(win.ScrollTrigger)gsap.registerPlugin(win.ScrollTrigger);
    const find=selector=>record.node.querySelector(selector);
    const all=selector=>[...record.node.querySelectorAll(selector)];
    record.context=gsap.context(()=>{},record.node);
    record.context.add(()=>{
      const tl=gsap.timeline({id:'qm-feature-entrance-'+record.scene,paused:true,defaults:{ease:'power3.out'},onComplete:()=>{
        record.arrived=true;record.ended=true;applyPlayback(record);
      }});
      record.timeline=tl;
      const camera=find('[data-ft-camera]'),arrivals=all('[data-ft-arrive]');
      const poses={qa:[1.58,-138,28],scope:[1.35,-90,0],counter:[1.72,-174,38],replay:[1.75,-166,58],assets:[1.52,110,40]};
      const pose=poses[record.scene];
      tl.fromTo(camera,{scale:pose[0],x:pose[1],y:pose[2],svgOrigin:'540 232'},{scale:.94,x:0,y:0,duration:2.05,ease:'power3.inOut'},0);
      tl.to(camera,{scale:1,x:0,y:0,duration:1.15,ease:'power2.out'},2.05);
      const spread=record.host.closest('[data-feature-spread]');
      const field=spread?.querySelector('[data-feature-field]');
      if(field)tl.fromTo(field,{clipPath:'polygon(100% 0,100% 0,100% 100%,100% 100%)'},{clipPath:'polygon(0 0,100% 0,100% 100%,0 100%)',duration:1.08,ease:'power4.inOut'},0);
      const title=spread?.querySelector('[data-feature-title-mask]');
      if(title)tl.fromTo(title,{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)',duration:1.1,ease:'power3.inOut'},.08);
      const typography=spread?.querySelector('[data-feature-type]');
      if(typography)tl.fromTo(typography,{x:-110,opacity:0},{x:0,opacity:.065,duration:1.9,ease:'power3.out'},.35);
      const aperture=find('[data-ft-aperture]');
      const apertureStart={qa:{x:-75,width:0},scope:{y:230,height:0},counter:{r:0},replay:{x:1175,width:0},assets:{y:590,height:0}}[record.scene];
      const apertureEnd=record.scene==='counter'?{r:900}:{x:-75,y:-130,width:1250,height:720};
      if(aperture)tl.fromTo(aperture,{attr:apertureStart},{attr:apertureEnd,duration:1.42,ease:'power4.inOut'},.16);
      if(record.scene==='qa') {
        tl.fromTo(arrivals,{x:i=>i<3?-160:110,y:i=>i<3?(i-1)*40:30,rotation:i=>i<3?-12:5,opacity:0},{x:0,y:0,rotation:0,opacity:1,duration:1.15,stagger:.13},.12);
        tl.fromTo(find('[data-ft-qa-thread]'),{opacity:0,strokeDasharray:'8 12',strokeDashoffset:120},{opacity:.46,strokeDashoffset:0,duration:1.35},.7);
      } else if(record.scene==='scope') {
        tl.fromTo(arrivals,{x:i=>i%2?-330:300,opacity:0},{x:0,opacity:1,duration:1.3,stagger:.12},.12);
        tl.fromTo(find('[data-ft-scope-guide]'),{scaleY:0,svgOrigin:'568 226'},{scaleY:1,duration:1.1},.85);
        tl.fromTo(find('[data-ft-scope-measure]'),{x:90,opacity:0},{x:0,opacity:1,duration:1},1.1);
      } else if(record.scene==='counter') {
        tl.fromTo(find('[data-ft-source-paper]'),{x:-75,opacity:0},{x:0,opacity:1,duration:1.3},.3);
        tl.fromTo(arrivals,{x:i=>i?-20:-100,y:i=>i?100:-80,rotation:i=>i?25:-18,opacity:0},{x:0,y:0,rotation:0,opacity:1,duration:1.6,stagger:.22},.1);
      } else if(record.scene==='replay') {
        tl.fromTo(arrivals,{x:i=>180+i*105,y:i=>-95-i*30,scale:.58,opacity:0},{x:0,y:0,scale:1,opacity:1,duration:1.65,stagger:{each:.17,from:'end'}},.08);
      } else {
        tl.fromTo(arrivals,{x:i=>(i%2?1:-1)*170,y:i=>i<2?-110:95,rotation:i=>(i%2?1:-1)*19,scale:.72,opacity:0},{x:0,y:0,rotation:0,scale:1,opacity:1,duration:1.5,stagger:.13},.1);
        tl.fromTo(find('[data-ft-index-hub]'),{scale:.3,opacity:0,svgOrigin:'0 0'},{scale:1,opacity:1,duration:1.3},.65);
        tl.fromTo(find('[data-ft-index-network]'),{opacity:0},{opacity:1,duration:1.1},.9);
      }
      tl.to({}, {duration:.01},3.19);
      const ambient=gsap.timeline({id:'qm-feature-ambient-'+record.scene,paused:true,repeat:-1,defaults:{ease:'sine.inOut'}});
      record.ambient=ambient;
      const drift=(node,out,start,duration,back)=>{
        ambient.fromTo(node,{x:0,y:0,rotation:0},Object.assign({duration,immediateRender:false},out),start);
        ambient.to(node,{x:0,y:0,rotation:0,duration},back);
      };
      const floats=all('[data-ft-float]');
      if(record.scene==='qa') {
        floats.forEach((node,i)=>drift(node,{x:i<3?35:-22,y:i<3?(i-1)*15:-16,rotation:i<3?(i-1)*2.3:1.7},.5+i*.19,3.3,7.5+i*.1));
        ambient.fromTo(find('[data-ft-qa-thread]'),{strokeDashoffset:0},{strokeDashoffset:-80,duration:profile.cycle,ease:'none',immediateRender:false},0);
        if(win.MotionPathPlugin){
          const pulse=find('[data-ft-pulse]');ambient.set(pulse,{opacity:0},0);
          ambient.to(pulse,{opacity:1,duration:.5},1.3);
          ambient.fromTo(pulse,{motionPath:{path:'M209 138 C410 102 362 219 521 226 S698 141 874 192',start:0,end:0}},{motionPath:{path:'M209 138 C410 102 362 219 521 226 S698 141 874 192',start:0,end:1},duration:5.1,ease:'power1.inOut',immediateRender:false},1.3);
          ambient.to(pulse,{opacity:0,duration:.5},6.1);
        }else ambient.set(find('[data-ft-pulse]'),{opacity:0},0);
      } else if(record.scene==='scope') {
        floats.forEach((node,i)=>{
          ambient.fromTo(node,{x:0},{x:[72,-52,86,-66,48,-38][i],duration:2.5,immediateRender:false},.4+i*.18);
          ambient.to(node,{x:0,duration:2.2,ease:'power2.inOut'},5+i*.12);
          ambient.to(node,{x:[-19,23,-26,18,-30,16][i],duration:1.8},10+i*.08);
          ambient.to(node,{x:0,duration:1.6},13+i*.08);
        });
        ambient.fromTo(find('[data-ft-scope-guide]'),{x:0},{x:92,duration:4,repeat:1,yoyo:true,immediateRender:false},3);
      } else if(record.scene==='counter') {
        drift(floats[0],{x:-78,y:-25,rotation:-13},.6,4.2,9.8);
        drift(floats[1],{x:-62,y:-26,rotation:-10},1.5,4.0,10.0);
        drift(find('[data-ft-source-detail]'),{x:18,y:8,rotation:0},1.5,4,10);
        if(win.MorphSVGPlugin){
          ambient.to(find('[data-ft-fold]'),{morphSVG:{shape:'M134 328 L165 215 L252 260 Z',shapeIndex:0},duration:2.1,ease:'power2.inOut'},3.6);
          ambient.to(find('[data-ft-fold]'),{morphSVG:{shape:'M175 328 L177 260 L252 260 Z',shapeIndex:0},duration:2.1,ease:'power2.inOut'},11.2);
        }
      } else if(record.scene==='replay') {
        floats.forEach((node,i)=>drift(node,{x:(i-1)*55,y:-(i+1)*12,rotation:0},.8+(2-i)*.4,4.1,12+(2-i)*.3));
        const light=find('[data-ft-archive-light]');ambient.set(light,{opacity:0,x:-150},0);
        ambient.to(light,{opacity:.65,duration:2},3.5).to(light,{x:230,duration:5.5,ease:'power1.inOut'},3.5).to(light,{opacity:0,duration:2},8.2).set(light,{x:-150},11);
      } else {
        floats.forEach((node,i)=>drift(node,{x:[-29,18,33,-19][i],y:[-30,-43,-22,24][i],rotation:[-3.5,2.6,3.5,-2][i]},.5+i*.6,3.6,10.5+i*.35));
        ambient.fromTo(find('[data-ft-index-hub]'),{y:0},{y:-9,duration:4,repeat:1,yoyo:true,immediateRender:false},2);
        const pulse=find('[data-ft-index-pulse]');ambient.set(pulse,{opacity:0},0);
        if(win.MotionPathPlugin){
          ambient.to(pulse,{opacity:1,duration:.4},2);
          ambient.fromTo(pulse,{motionPath:{path:'M231 197 L490 263 L576 268 L822 202',start:0,end:0}},{motionPath:{path:'M231 197 L490 263 L576 268 L822 202',start:0,end:1},duration:5.3,ease:'power1.inOut',immediateRender:false},2);
          ambient.to(pulse,{opacity:0,duration:.4},7);
        }
      }
      ambient.to({}, {duration:.01},profile.cycle-.01);
      record.quick=all('[data-ft-parallax]').map(node=>({depth:node.getAttribute('data-ft-parallax')==='front'?1:.38,
        x:gsap.quickTo(node,'x',{duration:.8,ease:'power3.out'}),y:gsap.quickTo(node,'y',{duration:.8,ease:'power3.out'})}));
      record.response=all('[data-ft-response]').map(node=>{
        gsap.set(node,{transformOrigin:'50% 50%'});
        // quickTo/resetTo requires real CSSPlugin properties, not the scale alias.
        return {node,name:node.getAttribute('data-ft-response'),quick:Object.fromEntries(['x','y','scaleX','scaleY','rotation','opacity'].map(key=>[key,gsap.quickTo(node,key,{duration:.85,ease:'power3.inOut'})]))};
      });
      if(win.ScrollTrigger?.create){
        const scroller=record.host.closest('[data-testid="stMain"]')||win;
        // The single existing scroll layer withdraws the artwork to the side.
        // Camera/ambient layers keep their own transforms and native geometry
        // remains constant. No pin, scroll capture or animated height.
        record.scrollTween=gsap.fromTo(find('[data-ft-scroll]'),{y:0,xPercent:0,scale:1,transformOrigin:'86% 54%'},{y:-profile.scroll*.8,xPercent:24,scale:.76,ease:'none',paused:true,duration:1});
        record.scrollTrigger=win.ScrollTrigger.create({trigger:find('.ft-stage'),scroller,animation:record.scrollTween,start:'clamp(top top+=140)',end:'clamp(bottom top+=72)',scrub:.45,pin:false,markers:false,invalidateOnRefresh:true});
        record.scrollTrigger.disable(false);record.scrollEnabled=false;
      }
    });
    setupReadingContext(record);
    record.syncAttention?.();
    if(record.static)settleInline(record);
  }

  function settleInline(record,{preserveScroll=false}={}){
    if(record.handoff)finishHandoff(record);
    settleResponse(record);
    record.attentionTween?.kill();
    record.timeline?.progress(1,true).pause();record.ambient?.pause(0,true);
    record.arrived=true;record.ended=true;record.paused=true;
    record.quick?.forEach(({x,y})=>{x.tween.pause();y.tween.pause();});
    if(record.context)win.gsap.set(record.node.querySelectorAll(preserveScroll?'[data-ft-parallax]':'[data-ft-parallax],[data-ft-scroll]'),{x:0,xPercent:0,y:0,rotation:0,scale:1});
  }
  function setupMotion(record) {
    if (record.inline) {setupInlineMotion(record);return;}
    const gsap = win.gsap;
    record.static = quiet() || !gsap?.timeline;
    if (!gsap?.timeline) { record.paused=true;record.ended=true;syncControls(record);setState(record);return; }
    if (win.MorphSVGPlugin) gsap.registerPlugin(win.MorphSVGPlugin);
    if (win.MotionPathPlugin) gsap.registerPlugin(win.MotionPathPlugin);
    const find = selector => record.node.querySelector(selector);
    const all = selector => [...record.node.querySelectorAll(selector)];
    const cards = all('[data-ft-card]'), tokens = all('[data-ft-token]'), rulers = all('[data-ft-ruler]');
    const camera = find('[data-ft-camera]'), shape = find('[data-ft-core]');
    const foreground = find('[data-ft-foreground]');
    // Assign the context before constructing plugins so a failed plugin can
    // still be reverted completely by the static fallback.
    record.context = gsap.context(() => {},record.node);
    record.context.add(() => {
      const tl = gsap.timeline({paused:true,defaults:{duration:1,ease:'power3.inOut'},onUpdate:()=>syncControls(record),onComplete:()=>{record.ended=true;record.paused=true;setState(record);}});
      record.timeline = tl;
      tl.addLabel('unfold',0).addLabel('connect',3.5).addLabel('focus',7.8);
      // A broad paper sweep establishes depth; the reading interface never moves.
      tl.fromTo(foreground,{x:-80,y:20,rotation:-22},{x:1700,y:70,rotation:-12,duration:1.35,ease:'power3.inOut'},0);
      tl.fromTo(camera,{scale:1.16,x:-49,y:-26,transformOrigin:'50% 50%'},{scale:1,x:0,y:0,duration:1.8,ease:'power3.out'},.1);
      if(cards.length) tl.fromTo(cards,{y:i=>i%2?-200:210,x:i=>(i-(cards.length-1)/2)*290,rotation:i=>i%2?27:-28,opacity:0},{y:0,x:0,rotation:0,opacity:1,duration:1.55,stagger:.14,ease:'power4.out'},.25);
      if(tokens.length) tl.fromTo(tokens,{opacity:0,scale:.5,transformOrigin:'50% 50%'},{opacity:1,scale:1,duration:.8,stagger:.16},2.1);
      tl.fromTo(find('[data-ft-core-wrap]'),{scale:.5,opacity:0,rotation:-35,transformOrigin:'50% 50%'},{scale:1,opacity:1,rotation:0,duration:1.5},1.1);
      tl.fromTo(find('[data-ft-core-detail]'),{opacity:0},{opacity:1,duration:.6},9);
      tl.fromTo(find('[data-ft-connect]'),{opacity:0,strokeDashoffset:120},{opacity:1,strokeDashoffset:0,duration:2.2,ease:'power1.out'},3.5);
      if(win.MorphSVGPlugin) {
        tl.set(shape,{attr:{d:record.spec.shapes[0]}},0);
        tl.to(shape,{morphSVG:{shape:record.spec.shapes[1],shapeIndex:0},duration:1.7,ease:'power2.inOut'},3.5);
        tl.to(shape,{morphSVG:{shape:record.spec.shapes[2],shapeIndex:0},duration:1.65,ease:'power2.inOut'},7.8);
      }
      if(win.MotionPathPlugin) {
        const a=find('[data-ft-traveller]'), b=find('[data-ft-traveller-secondary]');
        tl.set([a,b],{opacity:0},0);
        tl.to(a,{opacity:1,duration:.15},3.6).to(a,{motionPath:{path:record.spec.motion,autoRotate:true},duration:3.7,ease:'power1.inOut'},3.6).to(a,{opacity:0,duration:.25},7.3);
        tl.to(b,{opacity:1,duration:.15},4.5).to(b,{motionPath:{path:record.spec.motion,autoRotate:true},duration:3.25,ease:'power1.inOut'},4.5).to(b,{opacity:0,duration:.2},7.75);
      } else tl.set(all('[data-ft-traveller],[data-ft-traveller-secondary]'),{opacity:0},0);
      if(record.scene==='scope') {
        tl.fromTo(rulers,{x:i=>i%2?-390:330,y:i=>(i-2.5)*24,rotation:i=>i%2?12:-12,opacity:0},{x:i=>[36,-28,63,-13,43,0][i],y:0,rotation:0,opacity:1,stagger:.14,duration:1.35,ease:'power3.out'},.2);
        tl.to(rulers,{x:0,stagger:.11,duration:1.3},3.8);
        tl.fromTo(find('[data-ft-guide]'),{scaleY:0,transformOrigin:'50% 50%'},{scaleY:1,duration:1.5,ease:'power2.out'},4.3);
        tl.to(camera,{scale:1.045,x:-12,y:-5,duration:2.0},7.8);
      } else if(record.scene==='counter') {
        tl.fromTo(find('[data-ft-back-sheet]'),{rotation:20,x:-70,y:55,opacity:0},{rotation:0,x:0,y:0,opacity:1,duration:1.5},2.3);
        tl.to(cards[0],{x:-42,y:-12,rotation:-6,duration:1.5},3.5).to(cards[1],{x:38,y:9,rotation:5,duration:1.5},3.5);
        tl.to(find('[data-ft-back-sheet]'),{x:56,y:-32,rotation:-14,opacity:.35,duration:1.7},3.6);
        tl.to(camera,{scale:1.105,x:-58,y:-13,duration:2.0},7.8);
        tl.to(find('[data-ft-core-wrap]'),{x:28,y:-5,rotation:-8,duration:1.6},7.9);
      } else if(record.scene==='qa') {
        tl.to(cards[0],{x:-31,y:16,rotation:-5,duration:1.5},3.6).to(cards[1],{x:31,y:-12,rotation:6,duration:1.5},3.6);
        tl.to(tokens,{y:i=>[14,-18,-11][i],rotation:i=>[8,-8,5][i],duration:1.4,stagger:.1},4);
        tl.to(camera,{scale:1.065,x:-22,y:-8,duration:1.9},7.8);
      } else if(record.scene==='replay') {
        tl.fromTo(find('[data-ft-film]'),{scaleX:0,transformOrigin:'50% 50%'},{scaleX:1,duration:1.3},.1);
        tl.to(cards,{x:i=>(i-1)*26,y:i=>i===1?-35:12,rotation:i=>(i-1)*-5,duration:1.4,stagger:.14},3.5);
        tl.fromTo(find('[data-ft-playhead]'),{x:0},{x:590,duration:5.8,ease:'none'},3.5);
        tl.to(camera,{scale:1.035,y:5,duration:1.8},7.8);
      } else {
        tl.fromTo(find('[data-ft-index]'),{y:160,opacity:0},{y:0,opacity:1,duration:1.3,ease:'power3.out'},.15);
        tl.to(cards,{y:i=>[-23,-37,-37,-23][i],x:i=>(i-1.5)*14,rotation:i=>(i-1.5)*7,duration:1.45,stagger:.1},3.5);
        tl.to(cards,{y:7,x:0,rotation:0,duration:1.7,stagger:.09},7.8);
        tl.to(camera,{scale:1.025,y:-5,duration:1.7},7.8);
      }
      tl.to({}, {duration:1.1},10.0);
      record.quick = all('[data-ft-parallax]').map(node => {
        const depth = node.getAttribute('data-ft-parallax')==='front'?1:.35;
        return {depth,x:gsap.quickTo(node,'x',{duration:.65,ease:'power3.out'}),y:gsap.quickTo(node,'y',{duration:.65,ease:'power3.out'})};
      });
    });
    if(record.static) {record.timeline.progress(1).pause();record.ended=true;record.paused=true;}
    else if(canPlay(record) && !record.paused) record.timeline.play(0);
    setState(record);
  }
  function refreshMode() {
    for (const record of records()) {
    if(!record.timeline) continue;
    const wasStatic=record.static;
    record.static=quiet();
    if(record.inline){
      if(record.static)settleInline(record);
      else if(wasStatic){record.paused=false;record.arrived=true;}
      applyPlayback(record);continue;
    }
    if(record.static) {
      record.timeline.progress(1).pause();record.paused=true;record.ended=true;
      record.quick?.forEach(({x,y})=>{x.tween.pause();y.tween.pause();});
      win.gsap.set(record.node.querySelectorAll('[data-ft-parallax]'),{x:0,y:0});
    } else if(wasStatic) {record.paused=true;record.ended=true;}
    applyPlayback(record);
    }
  }
  function close(options={}) {
    const record=current;
    if(!record) return;
    current=null;
    record.abort.abort();
    record.context?.revert();
    record.timeline?.kill();
    if(record.node.open && typeof record.node.close==='function') record.node.close();
    record.node.remove();
    notify(false);
    inlineRecords.forEach(applyPlayback);
    if(options.restoreFocus!==false) {
      const trigger=record.trigger?.isConnected?record.trigger:doc.querySelector('[data-feature-theater-open="'+record.scene+'"]');
      trigger?.focus({preventScroll:true});
    }
  }
  function bindRecord(record) {
    const node=record.node;
    const find=selector=>node.querySelector(selector);
    Object.assign(record,{caption:find('.ft-caption'),scrub:find('[data-ft-scrub]'),time:find('[data-ft-time]'),pause:find('[data-ft-pause]'),replay:find('[data-ft-replay]'),status:find('[data-ft-status]'),chapters:[...node.querySelectorAll('[data-ft-chapter]')]});
    const eventOptions={signal:record.abort.signal};
    if(record.inline){
      const work=record.host.closest('[data-testid="stMain"]');
      record.syncAttention=()=>{
        const target=doc.activeElement;
        const attentive=Boolean(work && work.contains(target) && !record.host.contains(target) && target?.matches?.('input,textarea,select,[contenteditable="true"],[role="combobox"]'));
        if(record.attentive===attentive && record.ambient)return;
        record.attentive=attentive;
        record.attentionTween?.kill();
        if(record.ambient && !record.static && canPlay(record)){
          record.context.add(()=>{record.attentionTween=win.gsap.to(record.ambient,{timeScale:attentive?.28:1,duration:.45,ease:'power2.out',overwrite:true});});
        }else record.ambient?.timeScale(attentive?.28:1);
      };
      // Scope the decision to this page's real controls; deferred focusout sees
      // the new active element without observing or rewriting input values.
      doc.addEventListener('focusin',record.syncAttention,eventOptions);
      doc.addEventListener('focusout',()=>queueMicrotask(()=>{if(live(record))record.syncAttention();}),eventOptions);
    }
    if(!record.inline)node.addEventListener('click',event=>{
      if(event.target.closest('[data-ft-close]') && !record.inline)close();
      else if(event.target.closest('[data-ft-replay]') && !record.static && !record.held) {record.ended=false;record.paused=false;record.timeline?.pause(0);applyPlayback(record);}
      else if(event.target.closest('[data-ft-pause]') && !record.static && !record.held) {
        if(record.ended) {record.ended=false;record.paused=false;record.timeline?.pause(0);}
        else record.paused=!record.paused;
        applyPlayback(record);
      } else {
        const chapter=event.target.closest('[data-ft-chapter]');
        if(chapter && !record.static && !record.held) {record.paused=true;record.ended=false;record.timeline?.seek([1.9,5.45,9.7][Number(chapter.dataset.ftChapter)]).pause();syncControls(record);applyPlayback(record);}
      }
    },eventOptions);
    record.scrub?.addEventListener('input',()=>{if(record.static||record.held)return;record.paused=true;record.ended=false;record.timeline?.progress(Number(record.scrub.value)/1000).pause();syncControls(record);applyPlayback(record);},eventOptions);
    // Cache the artboard bounds on entry/resize; pointermove performs no layout reads.
    const stage=find('.ft-stage');
    const measure=()=>{record.bounds=stage.getBoundingClientRect();};
    stage.addEventListener('pointerenter',measure,eventOptions);
    win.addEventListener('resize',measure,eventOptions);
    stage.addEventListener('pointermove',event=>{
      if(!canPlay(record) || record.handoff || event.pointerType==='touch' || !record.bounds?.width) return;
      const x=Math.max(-1,Math.min(1,(event.clientX-record.bounds.left)/record.bounds.width*2-1));
      const y=Math.max(-1,Math.min(1,(event.clientY-record.bounds.top)/record.bounds.height*2-1));
      const strength=record.attentive?.3:1;
      record.quick?.forEach(item=>{item.x(x*27*item.depth*strength);item.y(y*18*item.depth*strength);});
    },eventOptions);
    stage.addEventListener('pointerleave',()=>{if(canPlay(record)&&!record.handoff)record.quick?.forEach(item=>{item.x(0);item.y(0);});},eventOptions);
    record.measure=measure;
  }
  function startRecord(record) {
    try {setupMotion(record);} catch(error) {
      // A plugin failure keeps the complete authored final composition.
      record.scrollTrigger?.kill();record.context?.revert();record.timeline?.kill();record.ambient?.kill();record.scrollTween?.kill();
      clearReadingContext(record);
      record.timeline=null;record.ambient=null;record.scrollTrigger=null;
      record.static=true;record.paused=true;record.ended=true;record.node.dataset.motionFallback='true';syncControls(record);setState(record);
      win.console?.warn('Concept theater animation unavailable; static artwork retained.',error);
    }
    record.measure();
  }
  function open(scene,trigger) {
    if(disposed || !SPECS[scene]) return false;
    close({restoreFocus:false});
    const spec=SPECS[scene], node=doc.createElement('dialog');
    node.className='qm-feature-theater ft-'+scene;
    node.setAttribute('aria-labelledby','qm-ft-title');
    node.setAttribute('aria-describedby','qm-ft-description');
    node.setAttribute('data-qm-feature-theater',scene);
    node.innerHTML=markup(scene,spec);
    const record={scene,spec,node,trigger:trigger||doc.activeElement,route:route(),abort:new win.AbortController(),paused:false,ended:false,static:false,chapter:-1,second:-1,inline:false,held:false,visible:true};
    current=record;
    doc.body.appendChild(node);
    if(typeof node.showModal==='function') node.showModal();
    else {node.setAttribute('open','');node.setAttribute('aria-modal','true');}
    node.addEventListener('cancel',event=>{event.preventDefault();close();},{signal:record.abort.signal});
    node.addEventListener('close',()=>{if(current===record)close();},{signal:record.abort.signal});
    bindRecord(record);startRecord(record);
    node.querySelector('[data-ft-close]').focus({preventScroll:true});notify(true);
    inlineRecords.forEach(applyPlayback);
    return true;
  }
  const intersection = typeof win.IntersectionObserver==='function' ? new win.IntersectionObserver(entries=>{
    for(const entry of entries) {
      const record=[...inlineRecords.values()].find(item=>item.node===entry.target);
      if(!record)continue;
      record.visible=entry.isIntersecting;applyPlayback(record);
    }
  },{threshold:.08}) : null;
  function unmountInline(record,{save=true}={}) {
    if(!inlineRecords.has(record.host))return;
    if(save)inlineSnapshots.set(record.scene,{time:record.timeline?.time()||0,ambientTime:record.ambient?.totalTime()||0,arrived:record.arrived,paused:record.paused,ended:record.ended,static:record.static,handoffDone:Boolean(record.handoffDone)});
    inlineRecords.delete(record.host);intersection?.unobserve(record.node);
    clearReadingContext(record);
    record.abort.abort();record.handoff?.kill();record.scrollTrigger?.kill();record.context?.revert();record.timeline?.kill();record.ambient?.kill();record.scrollTween?.kill();record.node.remove();
    record.host.removeAttribute('data-feature-inline-mounted');
    notifyInline();
  }
  function setRoute(next) {
    const key=String(next??'');
    if(key===inlineRoute)return;
    inlineRoute=key;
    for(const record of [...inlineRecords.values()])unmountInline(record,{save:false});
    inlineSnapshots.clear();inlineContexts.clear();
  }
  function mountInline(host,{hold=false}={}) {
    if(disposed || !host?.isConnected)return null;
    const scene=host.getAttribute('data-feature-inline');
    if(!SPECS[scene])return null;
    let record=inlineRecords.get(host);
    if(record?.node.isConnected) {
      if(hold)record.held=true;
      record.refreshReading?.();
      applyPlayback(record);return record;
    }
    if(record)unmountInline(record);
    const spec=SPECS[scene],node=doc.createElement('section');
    node.className='qm-feature-inline ft-'+scene;
    node.setAttribute('data-qm-feature-inline',scene);
    node.setAttribute('role','group');node.setAttribute('aria-label',spec.name+'：功能概念动画');
    node.innerHTML=markup(scene,spec,true);
    record={scene,spec,node,host,route:inlineRoute,abort:new win.AbortController(),paused:false,ended:false,arrived:false,static:false,chapter:-1,second:-1,inline:true,held:true,visible:true};
    inlineRecords.set(host,record);host.appendChild(node);host.setAttribute('data-feature-inline-mounted','true');
    bindRecord(record);
    const bounds=node.getBoundingClientRect();
    record.visible=bounds.bottom>0 && bounds.top<(win.innerHeight||doc.documentElement.clientHeight||900);
    startRecord(record);
    const snapshot=inlineSnapshots.get(scene);
    if(snapshot && !record.static && record.timeline) {
      record.timeline.time(snapshot.time,true).pause();record.ambient?.totalTime(snapshot.ambientTime||0,true).pause();
      record.paused=snapshot.static ? false : snapshot.paused;record.ended=snapshot.ended;record.arrived=Boolean(snapshot.arrived);record.handoffDone=Boolean(snapshot.handoffDone);
    }
    const cachedContext=inlineContexts.get(scene);if(cachedContext)applyContext(record,cachedContext);
    record.held=Boolean(hold);applyPlayback(record);intersection?.observe(node);
    notifyInline();
    return record;
  }
  function syncInline(hosts,{hold=false}={}) {
    const keep=new Set([...hosts].filter(host=>host?.isConnected && SPECS[host.getAttribute('data-feature-inline')]));
    for(const record of [...inlineRecords.values()])if(!keep.has(record.host) || !record.node.isConnected)unmountInline(record);
    for(const host of keep)mountInline(host,{hold});
  }
  function releaseInline(host,{settle=false}={}) {
    const record=inlineRecords.get(host);
    if(!record)return false;
    record.held=false;
    const reportArrived=host.dataset.qmRouteArrival==='report';delete host.dataset.qmRouteArrival;
    if(settle || reportArrived){
      settleInline(record,{preserveScroll:reportArrived&&!settle&&!quiet()});
      // Cancelling a route cover resolves the entrance, not the living scene.
      // Visibility still gates both clocks through applyPlayback; quiet mode
      // and an unavailable engine retain the complete static composition.
      record.paused=record.static || quiet();
    }
    if(reportArrived&&!settle&&!record.handoffDone){
      try{if(startHandoff(record))return true;}catch(error){finishHandoff(record);win.console?.warn('Report fold unavailable; complete scene retained.',error);}
    }
    applyPlayback(record);return true;
  }
  function onClick(event) {
    const button=event.target.closest?.('[data-feature-theater-open]');
    if(!button || button.disabled) return;
    event.preventDefault();event.stopPropagation();open(button.getAttribute('data-feature-theater-open'),button);
  }
  function onKey(event) {
    if(!current) return;
    if(event.key==='Escape') {event.preventDefault();event.stopImmediatePropagation();close();}
    // Also contain focus in browsers where showModal is unavailable.
    else if(event.key==='Tab') {
      const elements=[...current.node.querySelectorAll('button:not(:disabled),input:not(:disabled)')];
      const first=elements[0],last=elements[elements.length-1];
      if(event.shiftKey && doc.activeElement===first) {event.preventDefault();last?.focus();}
      else if(!event.shiftKey && doc.activeElement===last) {event.preventDefault();first?.focus();}
    }
  }
  const mutation=new win.MutationObserver(records=>{
    for(const record of [...inlineRecords.values()])if(!record.host.isConnected || !record.node.isConnected)unmountInline(record);
    const record=current;
    if(!record || records.every(change=>record.node.contains(change.target))) return;
    if((record.trigger && !record.trigger.isConnected) || record.route!==route()) close();
  });
  mutation.observe(doc,{childList:true,subtree:true,attributes:true,attributeFilter:['data-studio-scene','data-studio-location','data-qm-motion-mode']});
  doc.addEventListener('click',onClick);
  doc.addEventListener('keydown',onKey,true);
  doc.addEventListener('visibilitychange',refreshMode);
  win.addEventListener('qm-motion-preference-change',refreshMode);
  media?.addEventListener('change',refreshMode);
  function dispose() {
    if(disposed) return;
    disposed=true;close({restoreFocus:false});mutation.disconnect();
    for(const record of [...inlineRecords.values()])unmountInline(record,{save:false});
    inlineSnapshots.clear();inlineContexts.clear();intersection?.disconnect();
    doc.removeEventListener('click',onClick);doc.removeEventListener('keydown',onKey,true);
    doc.removeEventListener('visibilitychange',refreshMode);
    win.removeEventListener('qm-motion-preference-change',refreshMode);
    media?.removeEventListener('change',refreshMode);
    win.removeEventListener('pagehide',dispose);
  }
  win.addEventListener('pagehide',dispose,{once:true});
  win.QMFeatureTheater={version:VERSION,get disposed(){return disposed;},open,close,dispose,setRoute,mountInline,syncInline,releaseInline,setContext,
    getInlineState:()=>[...inlineRecords.values()].map(record=>({scene:record.scene,route:record.route,time:record.timeline?.time()||0,progress:record.timeline?.progress()||0,
      entranceTime:record.timeline?.time()||0,entranceDuration:record.timeline?.duration()||0,arrived:Boolean(record.arrived),ambientTime:record.ambient?.totalTime()||0,
      motionProfile:PROFILES[record.scene].name,ambientDuration:record.ambient?.duration()||0,attentive:Boolean(record.attentive),ambientTimeScale:record.ambient?.timeScale()||0,
      contextRevision:record.contextRevision||0,responseRunning:Boolean(record.response?.some(item=>Object.values(item.quick).some(fn=>fn.tween.isActive()))),
      handoffRunning:Boolean(record.handoff&&!record.handoff.paused()),handoffProgress:record.handoffProgress||0,handoffKind:record.handoffDone?record.scene:null,
      ambientRunning:Boolean(record.ambient && !record.ambient.paused() && record.arrived && canPlay(record) && !record.paused),scrollActive:Boolean(record.scrollEnabled),
      readingVisible:Boolean(record.readingStrip&&!record.readingStrip.hidden),
      held:record.held,visible:record.visible,paused:record.paused,static:record.static,ended:record.ended,running:Boolean(canPlay(record) && !record.paused && ((record.handoff&&!record.handoff.paused()) || (record.timeline && !record.timeline.paused()) || (record.arrived && record.ambient && !record.ambient.paused())))})),
    getState:()=>({version:VERSION,open:Boolean(current),scene:current?.scene||null,static:Boolean(current?.static),paused:Boolean(current?.paused),chapter:current?.chapter??null,progress:current?.timeline?.progress()||0,plugins:{morph:Boolean(win.MorphSVGPlugin),path:Boolean(win.MotionPathPlugin)}})};
})(typeof window==='undefined'?globalThis:window);
