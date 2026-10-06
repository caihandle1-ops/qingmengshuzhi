(function(scope){
  'use strict';
  const labels=Object.freeze({understand:'识别问题',retrieve:'查找资料',calculate:'计算分析',verify:'核验依据'});
  const statuses=Object.freeze({waiting:'未执行',running:'处理中',completed:'已执行',skipped:'不适用',blocked:'待确认',failed:'未完成'});
  const known=(map,key)=>typeof key==='string'&&Object.prototype.hasOwnProperty.call(map,key);
  function copyData(value){
    if(!value||typeof value.revision!=='string'||!Array.isArray(value.events)||!value.events.length||!Array.isArray(value.stages))return null;
    if(!value.events.every(e=>e&&known(labels,e.stage)&&known(statuses,e.status)))return null;
    const ids=Object.keys(labels);
    if(value.stages.length!==ids.length||!value.stages.every((s,i)=>s&&s.id===ids[i]&&known(statuses,s.status)))return null;
    const events=value.events.map(e=>Object.freeze({stage:e.stage,status:e.status,
      detail:typeof e.detail==='string'?e.detail:'未记录额外说明。',
      elapsed_ms:typeof e.elapsed_ms==='number'&&Number.isFinite(e.elapsed_ms)&&e.elapsed_ms>=0?e.elapsed_ms:null}));
    const stages=value.stages.map(s=>Object.freeze({id:s.id,label:labels[s.id],status:s.status,detail:typeof s.detail==='string'?s.detail:''}));
    return Object.freeze({revision:value.revision,run_id:typeof value.run_id==='string'?value.run_id:'',
      status:typeof value.status==='string'?value.status:'unknown',message:typeof value.message==='string'?value.message:'',
      events:Object.freeze(events),stages:Object.freeze(stages)});
  }
  function statesAt(data,index){
    if(index>=data.events.length)return data.stages.map(s=>({...s}));
    const stages=Object.entries(labels).map(([id,label])=>({id,label,status:'waiting',detail:''}));
    const limit=Number.isFinite(index)?Math.max(0,Math.round(index)):0;
    for(const event of data.events.slice(0,limit+1)){const node=stages.find(s=>s.id===event.stage);if(node&&known(statuses,event.status)){node.status=event.status;node.detail=event.detail;}}
    return stages;
  }
  function createPlayback({schedule,cancel,onChange,reduced=()=>false,visible=()=>true}){
    let data=null,index=0,timer=null,playing=false,disposed=false,generation=0;
    function pause(){generation++;if(timer!==null)cancel(timer);timer=null;playing=false;}
    function snapshot(){return{data,index,playing,states:data?statesAt(data,index):[]};}
    function publish(){onChange(snapshot());}
    function arm(){const token=generation;timer=schedule(()=>tick(token),1000);}
    function tick(token){
      if(disposed||token!==generation||!playing)return;
      timer=null;
      if(!visible()||reduced()){pause();publish();return;}
      index=Math.min(data.events.length,index+1);
      if(index===data.events.length)pause();
      publish();
      if(playing&&!disposed)arm();
    }
    return{snapshot,setData(value){
      if(disposed||data?.revision===value?.revision)return;
      const next=copyData(value);if(!next)return;
      pause();data=next;index=next.events.length;publish();
    },seek(value){
      if(!data||disposed||!Number.isFinite(value))return;
      pause();index=Math.max(0,Math.min(data.events.length,Math.round(value)));publish();
    },toggle(){
      if(!data||disposed)return;
      if(playing||reduced()||!visible()){pause();publish();return;}
      if(index===data.events.length)index=0;
      playing=true;publish();
      if(playing&&!disposed)arm();
    },pause(){pause();if(!disposed)publish();},dispose(){pause();disposed=true;}};
  }
  const api={labels,statuses,statesAt,createPlayback};scope.QMExecutionReplay=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
