import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rankingIndex, buildPlayerRanking, renderPlayerRanking } from '../static/js/player-ranking.mjs';

const players = [
  { id: 'one', name: 'Jugador Uno', team_id: 'a' },
  { id: 'two', name: 'Jugador Dos', team_id: 'b' },
  { id: 'none', name: 'Jugador Sin Partidos', team_id: 'a' },
  { id: 'archived', name: 'Jugador Archivado', team_id: 'a', active: false }
];
const stats = { one: { played: 1, wins: 1, losses: 0 }, two: { played: 10, wins: 8, losses: 2, sets_won: 17, sets_lost: 6 } };

test('index rewards a reliable win rate over a single victory', () => {
  assert.ok(rankingIndex(8, 10) > rankingIndex(1, 1));
  assert.equal(rankingIndex(0, 0), 0);
  assert.equal(buildPlayerRanking(players, stats)[0].id, 'two');
});

test('filter selects roster team and excludes archived players, without ranking unplayed', () => {
  const ranking = buildPlayerRanking(players, stats, 'a');
  assert.deepEqual(ranking.map(p => p.id), ['one', 'none']);
  assert.equal(ranking[1].winRate, null);
  assert.equal(ranking[1].index, 0);
});

test('table shows full columns, sets, ratio and pending state', () => {
  const html = renderPlayerRanking(players, stats, [{ id: 'b', name: 'Equipo B' }]);
  for (const column of ['Ganados', 'Perdidos', 'Partidos jugados', 'Sets ganados', 'Sets perdidos', 'Victorias (%)', 'Índice ajustado']) assert.ok(html.includes(column));
  assert.match(html, /80,0 %/);
  assert.match(html, /Sin partidos/);
  assert.doesNotMatch(html, /Jugador Archivado/);
  assert.match(html, />17<\/td>/);
});

test('ties follow win rate, wins, set difference, won sets and name deterministically', () => {
  const list = [{id:'b',name:'Beatriz',team_id:'a'}, {id:'a',name:'Alba',team_id:'a'}];
  const values = {a:{played:3,wins:2,losses:1,sets_won:4,sets_lost:3},b:{played:3,wins:2,losses:1,sets_won:5,sets_lost:2}};
  assert.equal(buildPlayerRanking(list, values)[0].id, 'b');
  values.a = {...values.b};
  assert.equal(buildPlayerRanking(list, values)[0].id, 'a');
});

test('empty team and escaped names do not fabricate or interpret data', () => {
  assert.match(renderPlayerRanking(players, stats, [], 'missing'), /No hay jugadores/);
  const html = renderPlayerRanking([{id:'x',name:'<img onerror="x">',team_id:'a'}], {}, []);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});
