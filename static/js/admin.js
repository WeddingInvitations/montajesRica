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

  document.querySelectorAll('[data-match-form]').forEach((form) => {
    const teamSelect = form.querySelector('[data-team-select]');
    const playerSelects = form.querySelectorAll('[data-player-select]');
    const editingMatch = form.dataset.matchEditing === 'true';
    if (!teamSelect) return;

    const filterPlayers = (clearOtherTeams) => {
      const teamId = teamSelect.value;
      playerSelects.forEach((select) => {
        Array.from(select.options).forEach((option) => {
          const belongsToTeam = option.dataset.team === teamId;
          const archivedSelection = editingMatch && option.dataset.active === 'false' && option.selected;
          option.disabled = option.value !== '' && (!belongsToTeam || (option.dataset.active === 'false' && !archivedSelection));
          if (!belongsToTeam && clearOtherTeams) option.selected = false;
        });
      });
    };

    filterPlayers(false);
    teamSelect.addEventListener('change', () => filterPlayers(true));
  });
})();
