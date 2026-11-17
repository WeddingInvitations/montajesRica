import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/js/pairing-order.js',import.meta.url),'utf8');

test('cambiar localía reordena campos e invierte sets y resultado sin perder jugadores',()=>{
  let change;
  const home = {checked:true,addEventListener(event,callback){change=callback;}};
  const mr = {players:['uno','dos']}, rival = {}, input={value:'6-4, 7-5'}, score={value:'12-0'};
  const sets={querySelector:()=>input};
  const nodes={'[data-pair-mr]':mr,'[data-pair-rival]':rival,'[data-pair-sets]':sets,
    '[data-pair-mr-title]':{},'[data-pair-rival-title]':{},'[data-pair-sets-title]':{}};
  const children=[mr,rival,sets];
  const row={querySelector:selector=>nodes[selector],insertBefore(node,before){children.splice(children.indexOf(node),1);children.splice(children.indexOf(before),0,node);}};
  const form={querySelector:selector=>selector==='[data-match-home]'?home:score};
  const editor={closest:()=>form,querySelectorAll:()=>[row]};
  vm.runInNewContext(source,{document:{querySelectorAll:()=>[editor]}});
  assert.equal(input.value,'6-4, 7-5');
  home.checked=false;change();
  assert.deepEqual(children,[rival,mr,sets]);
  assert.equal(input.value,'4-6, 5-7');
  assert.equal(score.value,'0-12');
  assert.equal(nodes['[data-pair-sets-title]'].textContent,'Sets (rival–MR)');
  assert.deepEqual(mr.players,['uno','dos']);
  change();assert.equal(input.value,'4-6, 5-7');
  home.checked=true;change();
  assert.deepEqual(children,[mr,rival,sets]);
  assert.equal(input.value,'6-4, 7-5');
  assert.equal(score.value,'12-0');
});