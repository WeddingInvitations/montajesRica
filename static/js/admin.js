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
      playerSelects.forEach((select) => {
        const previousValue = select.value;
        const options = originalOptions.get(select)
          .filter(({ element: option, historical }) => option.value === '' || (
            option.dataset.team === teamId
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
  });
})();
