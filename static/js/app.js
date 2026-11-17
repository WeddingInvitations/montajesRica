import { renderMatchScoreboards } from './match-scoreboard.mjs';
import { renderPlayerRanking } from './player-ranking.mjs';
import { renderMatchOutcome } from './match-outcome.mjs';

(() => {
  const dataNode = document.getElementById('club-data');
  if (!dataNode) return;

  const club = JSON.parse(dataNode.textContent || '{}');
  if (!club) return;
  const themeToggle = document.getElementById('theme-toggle');
  const storedTheme = localStorage.getItem('montajes-rica-theme');
  const preferredTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const setTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    const dark = theme === 'dark';
    themeToggle.setAttribute('aria-label', dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro');
    themeToggle.setAttribute('title', dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro');
    themeToggle.setAttribute('aria-pressed', String(dark));
    themeToggle.querySelector('.theme-icon').textContent = dark ? '☀' : '☾';
    themeToggle.querySelector('.theme-label').textContent = dark ? 'Claro' : 'Oscuro';
  };
  setTheme(storedTheme === 'dark' || storedTheme === 'light' ? storedTheme : preferredTheme);
  const teams = Array.isArray(club.teams) ? club.teams : [];
  const players = Array.isArray(club.players) ? club.players : [];
  const playerStats = club.player_stats && typeof club.player_stats === 'object' ? club.player_stats : {};
  const matches = Array.isArray(club.matches) ? club.matches : [];
  const standings = Array.isArray(club.standings) ? club.standings : [];
  const teamColors = ['green', 'blue', 'orange'];
  const teamById = (id) => teams.find((team) => team.id === id);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
  const safe = (value, fallback = 'Por confirmar') => escapeHtml(value === null || value === undefined || value === '' ? fallback : value);
  const dateValue = (match) => match.date ? new Date(`${match.date}T${match.time || '12:00'}`) : null;
  const displayDate = (match) => {
    const date = dateValue(match);
    if (!date || Number.isNaN(date.getTime())) return 'Fecha por confirmar';
    return new Intl.DateTimeFormat('es-ES', { weekday: 'short', day: 'numeric', month: 'short' }).format(date);
  };
  const teamName = (id) => safe(teamById(id)?.name, 'Equipo por confirmar');
  const emptyState = (icon, title, text) => `<div class="empty-state"><span class="empty-icon">${icon}</span><strong>${title}</strong><p>${text}</p></div>`;

  function teamCard(team, index, large = false) {
    const teamPlayers = players.filter((player) => player.team_id === team.id);
    const teamMatches = matches.filter((match) => match.team_id === team.id);
    const upcoming = teamMatches.filter((match) => match.status !== 'played').length;
    const color = teamColors.includes(team.color) ? team.color : teamColors[index % teamColors.length];
    return `<article class="team-card team-${color} ${large ? 'team-card-large' : ''}">
      <div class="team-card-top"><span class="team-number">0${index + 1}</span><span class="team-season">${safe(team.season, club.season)}</span></div>
      <div class="team-emblem"><span>${safe(team.short_name, String(team.name || `Equipo ${index + 1}`).replace(/equipo/i, 'E').slice(0, 3).toUpperCase())}</span><i></i></div>
      <p class="eyebrow">${large ? safe(team.division, 'División por configurar') : 'MONTAJES RICA'}</p><h3>${safe(team.name)}</h3>
      <div class="team-card-meta"><span><b>${teamPlayers.length}</b> jugadores</span><span><b>${upcoming}</b> partidos pendientes</span></div>
      <a class="team-action" href="#equipos" data-view="equipos" data-team-id="${escapeHtml(team.id)}">Ver plantilla <span>↗</span></a>
    </article>`;
  }

  function matchCard(match, compact = false) {
    const isPlayed = match.status === 'played';
    const opponent = safe(match.opponent, 'Rival por confirmar');
    const score = match.score ? `<span class="match-score">${safe(match.score)}</span>` : '<span class="match-vs">VS</span>';
    const pairDetails = `<details class="match-pairings"><summary>Ver parejas y sets</summary><div class="pair-scoreboards">${renderMatchScoreboards(match, players)}</div></details>`;
    return `<article class="match-item ${compact ? 'match-item-compact' : ''}"><div class="match-row">
      <div class="match-date"><strong>${displayDate(match).split(' ')[1] || '—'}</strong><span>${displayDate(match).split(' ').slice(0, 1).join('')}</span></div>
      <div class="match-info"><span class="match-team-label">${teamName(match.team_id)} · ${isPlayed ? 'FINALIZADO' : 'PRÓXIMO'}</span><strong>${match.home ? 'Montajes Rica' : opponent}<span class="versus"> vs </span>${match.home ? opponent : 'Montajes Rica'}</strong><small>${safe(match.venue, 'Pista por confirmar')}${match.time ? ` · ${match.time}` : ''}</small></div>
      ${score}${renderMatchOutcome(match)}
    </div>${pairDetails}</article>`;
  }

  function standingsTable(rows) {
    if (!rows.length) return emptyState('▤', 'Clasificación pendiente', 'Añadiremos las posiciones cuando tengamos los datos de las divisiones.');
    const sorted = [...rows].sort((a, b) => Number(a.position || 999) - Number(b.position || 999));
    const extraFields = ['source_a', 'sets_won', 'sets_lost', 'sets_difference', 'games_won', 'games_lost', 'games_difference'];
    const hasExtras = rows.some(row => extraFields.some(field => row[field] !== undefined));
    const extraHeaders = hasExtras ? '<th>A</th><th>SG</th><th>SP</th><th>DS</th><th>JG</th><th>JP</th><th>DJ</th>' : '';
    return `<div class="table-scroll"><table class="standings-table"><thead><tr><th>POS</th><th>EQUIPO</th><th>PJ</th><th>PG</th><th>PP</th><th>PTS</th>${extraHeaders}</tr></thead><tbody>${sorted.map((row) => `<tr class="${row.is_club ? 'our-team' : ''}"><td><span class="position-badge">${safe(row.position, '—')}</span></td><td><strong>${safe(row.team_name)}</strong>${row.is_club ? '<span class="you-tag">MR</span>' : ''}</td><td>${safe(row.played, '—')}</td><td>${safe(row.wins, '—')}</td><td>${safe(row.losses, '—')}</td><td><strong>${safe(row.points, '—')}</strong></td>${hasExtras ? extraFields.map(field => `<td>${safe(row[field], '—')}</td>`).join('') : ''}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderOverview() {
    const upcoming = matches.filter((match) => match.status !== 'played').sort((a, b) => (dateValue(a) || Infinity) - (dateValue(b) || Infinity));
    document.getElementById('stats-grid').innerHTML = [
      ['◫', String(teams.length).padStart(2, '0'), 'Equipos'],
      ['♙', String(players.length).padStart(2, '0'), 'Jugadores'],
      ['◷', String(upcoming.length).padStart(2, '0'), 'Próximos partidos']
    ].map(([icon, value, label]) => `<article class="stat-card"><span class="stat-icon">${icon}</span><strong>${value}</strong><span>${label}</span></article>`).join('');
    document.getElementById('team-grid').innerHTML = teams.map((team, index) => teamCard(team, index)).join('');
    document.getElementById('upcoming-matches').innerHTML = upcoming.length ? upcoming.slice(0, 3).map((match) => matchCard(match, true)).join('') : emptyState('◷', 'Calendario por publicar', 'Todavía no hay partidos cargados para esta temporada.');
    const preview = standings.slice(0, 5);
    document.getElementById('standings-preview').innerHTML = standingsTable(preview);
  }

  function populateSelect(select, includeAll = false) {
    select.innerHTML = `${includeAll ? '<option value="all">Todos los equipos</option>' : ''}${teams.map((team) => `<option value="${escapeHtml(team.id)}">${safe(team.name)}</option>`).join('')}`;
  }

  function renderRoster(teamId) {
    const roster = players
      .filter((player) => player.team_id === teamId)
      .sort((left, right) => String(left.name || '').localeCompare(String(right.name || ''), 'es'));
    const team = teamById(teamId);
    document.getElementById('roster-title').textContent = `Jugadores · ${team?.name || 'Equipo'}`;
    const content = roster.length ? `<div class="roster-table-scroll"><table class="roster-table"><thead><tr><th scope="col">Jugador</th><th scope="col">Equipo</th><th scope="col">Lado</th><th scope="col">Partidos jugados</th><th scope="col">Ganados</th><th scope="col">Perdidos</th><th scope="col">Sets ganados</th><th scope="col">Sets perdidos</th></tr></thead><tbody>${roster.map((player) => {
      const stats = playerStats[player.id] || { played: 0, wins: 0, losses: 0, sets_won: 0, sets_lost: 0 };
      return `<tr><th scope="row">${safe(player.name)}</th><td>${teamName(player.team_id)}</td><td>${safe(player.handedness, 'Por confirmar')}</td><td class="roster-number">${stats.played}</td><td class="roster-number">${stats.wins}</td><td class="roster-number">${stats.losses}</td><td class="roster-number">${stats.sets_won}</td><td class="roster-number">${stats.sets_lost}</td></tr>`;
    }).join('')}</tbody></table></div>` : emptyState('♙', 'Plantilla por completar', 'Cuando tengamos los nombres y perfiles, podrás ver aquí quién juega en este equipo y su lado de pista.');
    document.getElementById('roster-content').innerHTML = content;
  }

  function renderMatches(teamId = 'all') {
    const list = matches.filter((match) => teamId === 'all' || match.team_id === teamId).sort((a, b) => (dateValue(a) || Infinity) - (dateValue(b) || Infinity));
    document.getElementById('matches-list').innerHTML = list.length ? list.map((match) => matchCard(match)).join('') : emptyState('◷', 'Aún no hay partidos', 'El calendario y los resultados aparecerán aquí cuando estén disponibles.');
  }

  function renderRanking(teamId = 'all') {
    document.getElementById('ranking-content').innerHTML = renderPlayerRanking(players, playerStats, teams, teamId);
    document.getElementById('ranking-title').textContent = teamId === 'all'
      ? 'Clasificación general' : `Clasificación · ${teamById(teamId)?.name || 'Equipo'}`;
  }

  function renderStandings(teamId = 'all') {
    const visibleTeams = teamId === 'all' ? teams : teams.filter((team) => team.id === teamId);
    const cards = visibleTeams.map(team => {
      const title = `${safe(team.division, 'División por configurar')} · ${safe(team.season, club.season)}`;
      const rows = standings.filter(row => row.team_id ? row.team_id === team.id : row.division === team.division && (!row.season || row.season === team.season));
      return `<section class="panel standings-card"><div class="panel-heading"><div><p class="eyebrow">${title}</p><h2>${safe(team.name)} · Tabla de posiciones</h2></div></div>${standingsTable(rows)}</section>`;
    }).join('');
    document.getElementById('standings-list').innerHTML = cards || emptyState('▤', 'Clasificación pendiente', 'Todavía no hay datos de liga para mostrar.');
  }

  function switchView(view) {
    const names = { inicio: 'Resumen', equipos: 'Equipos', partidos: 'Partidos', clasificacion: 'Clasificación', ranking: 'Ranking' };
    document.querySelectorAll('.view-section').forEach((section) => section.classList.toggle('hidden', section.id !== `view-${view}`));
    document.querySelectorAll('.nav-link').forEach((link) => link.classList.toggle('active', link.dataset.view === view));
    document.getElementById('current-section').textContent = names[view] || names.inicio;
    document.getElementById('sidebar').classList.remove('sidebar-open');
    document.getElementById('mobile-menu').setAttribute('aria-expanded', 'false');
    if (view === 'equipos' && !document.getElementById('team-select').value && teams[0]) renderRoster(teams[0].id);
  }

  document.getElementById('all-teams').innerHTML = teams.map((team, index) => teamCard(team, index, true)).join('');
  populateSelect(document.getElementById('team-select'));
  populateSelect(document.getElementById('match-team-filter'), true);
  populateSelect(document.getElementById('standings-team-filter'), true);
  populateSelect(document.getElementById('ranking-team-filter'), true);
  renderOverview();
  renderRoster(teams[0]?.id);
  renderMatches();
  renderStandings();
  renderRanking();

  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-view]');
    if (link) {
      event.preventDefault();
      const view = link.dataset.view;
      if (view === 'equipos' && link.dataset.teamId) document.getElementById('team-select').value = link.dataset.teamId;
      switchView(view);
      if (view === 'equipos') renderRoster(document.getElementById('team-select').value);
      history.replaceState(null, '', `#${view}`);
    }
  });
  document.getElementById('team-select').addEventListener('change', (event) => renderRoster(event.target.value));
  document.getElementById('match-team-filter').addEventListener('change', (event) => renderMatches(event.target.value));
  document.getElementById('standings-team-filter').addEventListener('change', (event) => renderStandings(event.target.value));
  document.getElementById('ranking-team-filter').addEventListener('change', (event) => renderRanking(event.target.value));
  document.getElementById('mobile-menu').addEventListener('click', (event) => {
    const opened = document.getElementById('sidebar').classList.toggle('sidebar-open');
    event.currentTarget.setAttribute('aria-expanded', String(opened));
  });
  themeToggle.addEventListener('click', () => {
    const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('montajes-rica-theme', nextTheme);
    setTheme(nextTheme);
  });
  const initialView = location.hash.slice(1);
  if (['equipos', 'partidos', 'clasificacion', 'ranking'].includes(initialView)) switchView(initialView);
})();
