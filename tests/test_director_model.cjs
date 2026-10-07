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
console.log('director model: navigation, rerender stability, selection, reorder and cleanup passed');
