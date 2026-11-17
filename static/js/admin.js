(() => {
  const adminTabs = Array.from(document.querySelectorAll('[data-admin-tab]'));
  const adminPanels = Array.from(document.querySelectorAll('.admin-section[role="tabpanel"]'));

  function activateAdminTab(tabName, updateUrl = true) {
    const activeTab = adminTabs.find((tab) => tab.dataset.adminTab === tabName);
    if (!activeTab) return;
    adminTabs.forEach((tab) => {
      const selected = tab === activeTab;
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    adminPanels.forEach((panel) => {
      const selected = panel.id === tabName;
      panel.classList.toggle('hidden', !selected);
      panel.hidden = !selected;
    });
    if (updateUrl) history.replaceState(null, '', `#${tabName}`);
  }

  adminTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activateAdminTab(tab.dataset.adminTab));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const nextIndex = event.key === 'Home' ? 0
        : event.key === 'End' ? adminTabs.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + adminTabs.length) % adminTabs.length;
      adminTabs[nextIndex].focus();
      activateAdminTab(adminTabs[nextIndex].dataset.adminTab);
    });
  });

  const initialTab = location.hash.slice(1);
  if (initialTab) activateAdminTab(initialTab, false);

  const rosterTeam = document.querySelector('[data-roster-team]');
  const rosterSearch = document.querySelector('[data-roster-search]');
  const rosterRows = Array.from(document.querySelectorAll('[data-roster-row]'));
  const normalize = (text) => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim();
  const filterRoster = () => {
    let visible = 0;
    rosterRows.forEach((row) => {
      const name = row.querySelector('[name="name"]').value;
      const team = row.querySelector('[name="team_id"]').value;
      const matches = (!rosterTeam.value || rosterTeam.value === team)
        && normalize(name).includes(normalize(rosterSearch.value));
      row.hidden = !matches;
      row.classList.toggle('hidden', !matches);
      if (matches) visible += 1;
    });
    const empty = document.querySelector('[data-roster-empty]');
    if (empty) empty.hidden = visible !== 0;
  };
  if (rosterTeam && rosterSearch) {
    rosterTeam.addEventListener('change', filterRoster);
    rosterSearch.addEventListener('input', filterRoster);
    rosterRows.forEach((row) => row.addEventListener('input', filterRoster));
  }

  document.querySelectorAll('[data-match-form]').forEach((form) => {
    const teamSelect = form.querySelector('[data-team-select]');
    const futureException = form.querySelector('[data-future-exception]');
    // The pair editor is a sibling of data-match-form, inside the same form.
    const playerSelects = form.closest('form').querySelectorAll('[data-player-select]');
    const editingMatch = form.dataset.matchEditing === 'true';
    if (!teamSelect) return;

    const originalOptions = new Map(Array.from(playerSelects, (select) => [
      select,
      Array.from(select.options, (option) => ({
        element: option.cloneNode(true),
        historical: editingMatch && option.selected && option.value !== ''
      }))
    ]));

    const filterPlayers = () => {
      const teamId = teamSelect.value;
      if (futureException) {
        futureException.disabled = teamId !== 'equipo-1';
        if (futureException.disabled) futureException.checked = false;
      }
      playerSelects.forEach((select) => {
        const previousValue = select.value;
        const options = originalOptions.get(select)
          .filter(({ element: option, historical }) => option.value === '' || (
            (option.dataset.team === teamId || (
              teamId === 'equipo-1' && futureException?.checked && option.dataset.team === 'equipo-2'
            ))
            && (option.dataset.active !== 'false' || historical)
          ))
          .map(({ element }) => {
            const option = element.cloneNode(true);
            option.disabled = false;
            option.selected = false;
            return option;
          });
        // Remove unrelated players rather than disabling them: native mobile
        // select menus may still display disabled/hidden options.
        select.replaceChildren(...options);
        select.value = options.some((option) => option.value === previousValue) ? previousValue : '';
      });
    };

    filterPlayers();
    teamSelect.addEventListener('change', filterPlayers);
    futureException?.addEventListener('change', filterPlayers);
  });
})();
