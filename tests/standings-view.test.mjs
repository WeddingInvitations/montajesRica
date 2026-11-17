import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8').replace(/^import .*;$/gm, '');

function render(metadata = {}, fixtures = []) {
  const teams = [{id:'equipo-1',name:'Equipo 500',division:'Por configurar',season:'Prueba'},
    {id:'equipo-2',name:'Equipo Future',division:'Por configurar',season:'Prueba'}];
  const club = {teams, players:[], matches:[], standings:[{team_id:'equipo-1',division:'Por configurar',season:'Prueba',
    position:1,team_name:'Equipo <prueba>',played:1,wins:0,losses:1,points:0,
    source_a:0,sets_won:0,sets_lost:2,sets_difference:-2,games_won:0,games_lost:12,games_difference:-12}]};
  teams.forEach(team => Object.assign(team, metadata));
  club.matches = fixtures;
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',value:'',listeners:{},
      setAttribute(){}, querySelector(){return {};}, classList:{toggle(){},remove(){}},
      addEventListener(event, callback){this.listeners[event] = callback;}});
    return nodes.get(id);
  };
  node('club-data').textContent = JSON.stringify(club);
  vm.runInNewContext(source, {document:{getElementById:node,documentElement:{dataset:{}},querySelectorAll:()=>[],addEventListener(){}},
    window:{matchMedia:()=>({matches:false})},localStorage:{getItem:()=>null},location:{hash:''},
    renderPlayerRanking:()=>'',renderMatchScoreboards:()=>'',renderMatchOutcome:()=>''});
  return nodes;
}

test('tablas se separan por equipo aunque compartan división provisional', () => {
  const nodes = render();
  const html = nodes.get('standings-list').innerHTML;
  assert.equal((html.match(/Equipo &lt;prueba&gt;/g) || []).length, 1);
  assert.match(html, /Equipo 500 · Tabla de posiciones/);
  assert.match(html, /Equipo Future · Tabla de posiciones/);
  assert.match(html, /Clasificación pendiente/);
});

test('filtro de equipo no muestra clasificaciones de otros equipos', () => {
  const nodes = render();
  nodes.get('standings-team-filter').listeners.change({target:{value:'equipo-2'}});
  assert.doesNotMatch(nodes.get('standings-list').innerHTML, /Equipo &lt;prueba&gt;/);
  nodes.get('standings-team-filter').listeners.change({target:{value:'equipo-1'}});
  assert.match(nodes.get('standings-list').innerHTML, /Equipo &lt;prueba&gt;/);
});

test('Excel conserva ceros, diferencias negativas y cabeceras de sets y juegos', () => {
  const html = render().get('standings-list').innerHTML;
  for (const header of ['A','SG','SP','DS','JG','JP','DJ']) assert.ok(html.includes(`<th>${header}</th>`));
  assert.match(html, /<td>0<\/td>/);
  assert.match(html, /<td>-2<\/td>/);
  assert.match(html, /<td>-12<\/td>/);
  assert.doesNotMatch(html, /<prueba>/);
});

test('no muestra metadatos por configurar ni sus contenedores vacíos', () => {
  const nodes = render({division:'División por configurar',season:'Por configurar'});
  for (const id of ['team-grid', 'all-teams', 'standings-list']) {
    const html = nodes.get(id).innerHTML;
    assert.doesNotMatch(html, /por configurar|por confirmar/i);
    assert.doesNotMatch(html, /<p class="eyebrow"><\/p>|<span class="team-season"><\/span>/);
  }
});

test('mantiene divisiones y temporadas reales y escapa su contenido', () => {
  const nodes = render({division:'División de prueba <ejemplo>',season:'2026/2027'});
  for (const id of ['all-teams', 'standings-list']) {
    const html = nodes.get(id).innerHTML;
    assert.match(html, /División de prueba &lt;ejemplo&gt;/);
    assert.match(html, /2026\/2027/);
  }
});

test('partidos agrupados por jornada numérica, ordenados por fecha dentro y con antiguos al final', () => {
  const fixtures = [
    {jornada:10,opponent:'Rival diez',date:'2026-01-01',team_id:'equipo-1'},
    {jornada:2,opponent:'Rival segundo',date:'2026-02-02',team_id:'equipo-1'},
    {opponent:'Rival antiguo',date:'2026-01-01',team_id:'equipo-1'},
    {jornada:2,opponent:'Rival primero',date:'2026-02-01',team_id:'equipo-2'},
  ];
  const nodes=render({},fixtures);
  const html=nodes.get('matches-list').innerHTML;
  assert.ok(html.indexOf('Jornada 2') < html.indexOf('Jornada 10'));
  assert.ok(html.indexOf('Jornada 10') < html.indexOf('Sin jornada asignada'));
  assert.ok(html.indexOf('Rival primero') < html.indexOf('Rival segundo'));
  assert.equal((html.match(/<h2 class="matchday-heading">Jornada 2/g)||[]).length,1);
  nodes.get('match-team-filter').listeners.change({target:{value:'equipo-2'}});
  const filtered=nodes.get('matches-list').innerHTML;
  assert.match(filtered,/Jornada 2/);
  assert.doesNotMatch(filtered,/Jornada 10|Sin jornada asignada|Rival segundo/);
});