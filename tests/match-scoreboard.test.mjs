import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderPairScoreboard, renderMatchScoreboards } from '../static/js/match-scoreboard.mjs';

test('pending pairing can expand with three empty sets and both sides', () => {
  const html = renderPairScoreboard({}, 0, [], 'Rival de prueba');
  assert.match(html, /<details class="pair-scoreboard">/);
  for (const number of [1, 2, 3]) assert.ok(html.includes(`Set ${number}`));
  assert.match(html, /Resultado pendiente/);
  assert.equal((html.match(/Sin resultado/g) || []).length, 6);
  assert.match(html, /Montajes Rica/);
  assert.match(html, /Pareja rival por confirmar/);
});

test('recorded scores preserve zero, historic names and pending third set', () => {
  const html = renderPairScoreboard({
    player_ids: ['one', 'two'], player_names: ['Nombre histórico', 'Jugador Dos'],
    opponent_pair: 'Rival Uno y Rival Dos', sets: [{ home: 6, away: 0 }, { home: 7, away: 5 }]
  }, 1, [{ id: 'one', name: 'Nombre modificado' }]);
  assert.match(html, /Partido 2/);
  assert.match(html, /Nombre histórico/);
  assert.doesNotMatch(html, /Nombre modificado/);
  assert.match(html, /class="set-score">0<\/td>/);
  assert.equal((html.match(/set-score-won/g) || []).length, 2);
  assert.equal((html.match(/Sin resultado/g) || []).length, 2);
});

test('no pairings gives an explicit pending grid without fabricated scores', () => {
  const html = renderMatchScoreboards({ pairings: [] });
  assert.match(html, /todavía no están configuradas/);
  assert.match(html, /Set 3/);
});

test('names are escaped and extra stored sets are not silently lost', () => {
  const html = renderPairScoreboard({ player_names: ['<img onerror="x">'],
    sets: Array.from({ length: 4 }, () => ({ home: 6, away: 4 })) });
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
  assert.match(html, /Set 4/);
});

test('local primero y visitante después con sus propios sets, sin alterar historial', () => {
  const pairing = {player_names:['Pareja MR de prueba'],opponent_pair:'Pareja rival de prueba',sets:[{home:6,away:2}]};
  for (const home of [true,false]) {
    const html = renderMatchScoreboards({home, opponent:'Equipo rival',pairings:[pairing]});
    const rows = html.split('<tbody>')[1].split('</tbody>')[0];
    const first = rows.split('</tr>')[0];
    assert.match(first, home ? /Pareja MR de prueba/ : /Pareja rival de prueba/);
    assert.match(first, home ? /set-score-won">6/ : /class="set-score">2/);
    const second = rows.split('</tr>')[1];
    assert.match(second, home ? /class="set-score">2/ : /set-score-won">6/);
    assert.equal(pairing.sets[0].home,6);
    assert.equal(pairing.sets[0].away,2);
  }
});
