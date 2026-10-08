'use strict';
const assert = require('node:assert/strict');
const {createDeck} = require('../app/director_frontend/director-model.js');
const payload = {revision:'one',chapters:['overview','metrics','annual','sources'].map(id=>({id,kind:id}))};
const history=[];
const deck=createDeck(state=>history.push(state));
assert.equal(deck.setPayload(payload),true);
assert.equal(deck.snapshot().active,'overview');
// Rapid back/forward commands must end at the latest request, not queue motion.
for(let i=0;i<40;i++){deck.go('sources');deck.step(-1);deck.go('overview');deck.go('metrics');}
assert.equal(deck.snapshot().active,'metrics');
assert.equal(history.at(-1).active,'metrics');
const before=history.length;
assert.equal(deck.setPayload(payload),false);
assert.equal(history.length,before,'unrelated Streamlit rerender must not replay entry');
// Reordering must retain the exact selected scene, never switch index meaning.
assert.equal(deck.move('metrics',1),true);
assert.equal(deck.snapshot().active,'metrics');
assert.equal(deck.snapshot().index,2);
assert.equal(history.at(-1).changed,false);
assert.equal(deck.toggle('metrics'),true);
assert.equal(deck.snapshot().active,'sources');
assert.equal(deck.snapshot().visible.includes('metrics'),false);
deck.toggle('overview');deck.toggle('annual');
assert.deepEqual(deck.snapshot().visible,['sources']);
assert.equal(deck.toggle('sources'),false,'cannot remove the final chapter');
assert.equal(deck.step(1),false);
assert.equal(deck.step(-1),false);
deck.reset();
assert.deepEqual(deck.snapshot().visible,['overview','metrics','annual','sources']);
assert.equal(deck.snapshot().active,'overview');
assert.equal(deck.setPayload({revision:'bad',chapters:[{id:'x',kind:'a'},{id:'x',kind:'b'}]}),false);
assert.equal(deck.snapshot().payload.revision,'one');
deck.dispose();const ended=history.length;
deck.go('annual');deck.step(1);deck.reset();deck.move('overview',1);deck.toggle('sources');deck.setPayload({...payload,revision:'two'});
assert.equal(history.length,ended,'disposed component must never publish');
const focused=createDeck();
focused.setPayload({...payload,focus:{metrics:[{id:'revenue'},{id:'net_profit'}],rows:[
  {year:2022,metrics:[{id:'revenue',value:0},{id:'net_profit',value:null}]},
  {year:2024,metrics:[{id:'revenue',value:73.6789},{id:'net_profit',value:-3.25}]}]}});
assert.equal(focused.snapshot().fact.value,73.6789);
focused.setFocus('net_profit',2022);assert.equal(focused.snapshot().fact.value,null);
assert.equal(focused.setFocus('revenue',2023),false,'missing year cannot become a synthesized observation');
assert.equal(focused.setFocus('invented',2024),false,'unknown metrics cannot be added by navigation');
focused.setFocus('net_profit',2024);
for(let i=0;i<40;i++){focused.go('annual');focused.go('sources');focused.go('metrics');assert.equal(focused.snapshot().fact.value,-3.25);}
assert.equal(focused.snapshot().focus.year,2024);
focused.move('metrics',1);focused.toggle('annual');assert.equal(focused.snapshot().fact.value,-3.25);
focused.dispose();assert.equal(focused.setFocus('revenue',2024),false);
console.log('director model: navigation, rerender stability, selection, reorder and cleanup passed');
