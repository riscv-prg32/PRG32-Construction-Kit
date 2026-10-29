// The admin Activity page (templates/admin_activity.html, prg32_construction_kit/activity.py).
// Left: who was active (accounts, and visitors without one under their one-day pseudonym).
// Right: the log, newest first, for everybody or for the person picked on the left.
(function () {
  const person = { user_id: '', visitor: '', label: '' };
  let nextBefore = null;

  function isoDay(date) { return date.toISOString().slice(0, 10); }

  function filters() {
    const query = new URLSearchParams();
    $('#activityFilter').serializeArray().forEach(field => { if (field.value) query.set(field.name, field.value); });
    if (person.user_id) query.set('user_id', person.user_id);
    if (person.visitor) query.set('visitor', person.visitor);
    return query;
  }

  function who(event) {
    if (event.actor === 'guest') {
      return event.visitor
        ? `<i class="bi bi-incognito" aria-hidden="true"></i> <code>${Kit.escape(event.visitor)}</code>`
        : `<span class="text-muted">${Kit.escape(tr('js.admin_activity.visitor_opted_out', 'visitor (do not track)'))}</span>`;
    }
    const icon = event.actor === 'token' ? 'bi-key' : 'bi-person';
    return `<i class="bi ${icon}" aria-hidden="true"></i> ${Kit.escape(event.username || ('#' + event.user_id))}`;
  }

  function outcome(status) {
    const badge = status >= 500 ? 'text-bg-danger' : status >= 400 ? 'text-bg-warning' : 'text-bg-success';
    return `<span class="badge ${badge}">${status}</span>`;
  }

  function row(event) {
    const when = new Date(event.created_at);
    return `<tr><td class="small text-nowrap" title="${Kit.escape(event.created_at)}">${Kit.escape(when.toLocaleString())}</td>
      <td class="small">${who(event)}</td><td><span class="badge text-bg-light">${Kit.escape(event.category)}</span></td>
      <td class="small"><code>${Kit.escape(event.method + ' ' + event.route)}</code>${event.object_id ? `<div class="text-muted">${Kit.escape(event.object_id)}</div>` : ''}</td>
      <td>${outcome(event.status)} <span class="small text-muted">${event.duration_ms}&nbsp;ms</span></td>
      <td class="small text-muted">${Kit.escape(event.agent)}<div>${Kit.escape(event.network)}</div></td></tr>`;
  }

  function loadEvents(more) {
    const query = filters();
    if (more && nextBefore) query.set('before', nextBefore);
    return Kit.api('/api/admin/activity?' + query.toString()).then(data => {
      $('#activityOff').toggleClass('d-none', data.enabled);
      const html = data.events.map(row).join('');
      if (more) $('#events').append(html);
      else $('#events').html(html || `<tr><td colspan="6" class="text-muted">${Kit.escape(tr('js.admin_activity.nothing_logged', 'Nothing logged for these filters.'))}</td></tr>`);
      nextBefore = data.next_before;
      $('#moreEvents').toggleClass('d-none', !nextBefore);
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  function personItem(kind, id, label, detail, count) {
    const active = (kind === 'user' && String(person.user_id) === String(id)) || (kind === 'visitor' && person.visitor === id);
    return `<button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-start${active ? ' active' : ''}"
      data-kind="${kind}" data-id="${Kit.escape(String(id))}" data-label="${Kit.escape(label)}">
      <span><span class="fw-semibold">${Kit.escape(label)}</span><span class="d-block small">${Kit.escape(detail)}</span></span>
      <span class="badge text-bg-primary rounded-pill">${count}</span></button>`;
  }

  function loadPeople() {
    const query = new URLSearchParams();
    ['from', 'to'].forEach(name => { const value = $(`#activityFilter [name="${name}"]`).val(); if (value) query.set(name, value); });
    return Kit.api('/api/admin/activity/people?' + query.toString()).then(data => {
      const users = data.users.map(item => personItem('user', item.user_id, item.username,
        tr('js.admin_activity.active_days', '{days} active day(s), last {when}', { days: item.active_days, when: new Date(item.last_seen).toLocaleString() }), item.requests));
      const guests = data.guests.map(item => personItem('visitor', item.visitor, item.visitor,
        [item.day, item.agent, item.network].filter(Boolean).join(' · '), item.requests));
      const header = text => `<div class="list-group-item small text-uppercase text-muted fw-semibold">${Kit.escape(text)}</div>`;
      $('#people').html([header(tr('js.admin_activity.accounts', 'Accounts')), ...users,
        header(tr('js.admin_activity.visitors', 'Visitors without an account (one pseudonym per day)')), ...guests].join(''));
      $('#peopleNote').text(tr('js.admin_activity.without_pseudonym', '{count} request(s) from visitors asking not to be tracked are counted without a pseudonym.',
        { count: data.guest_requests_without_pseudonym }));
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  function pick(kind, id, label) {
    person.user_id = kind === 'user' ? id : '';
    person.visitor = kind === 'visitor' ? id : '';
    person.label = label;
    $('#clearPerson').toggleClass('d-none', !kind);
    $('#logTitle').text(kind ? tr('js.admin_activity.log_of', 'Activity of {name}', { name: label }) : tr('js.admin_activity.log', 'Log'));
    $('#people .list-group-item-action').removeClass('active');
    if (kind) $(`#people [data-kind="${kind}"][data-id="${CSS.escape(String(id))}"]`).addClass('active');
    loadEvents(false);
  }

  $('#activityFilter').on('submit', function (event) {
    event.preventDefault();
    loadPeople();
    loadEvents(false);
  });
  $(document).on('click', '#people [data-kind]', function () {
    pick($(this).data('kind'), String($(this).data('id')), String($(this).data('label')));
  });
  $('#clearPerson').on('click', () => pick('', '', ''));
  $('#moreEvents').on('click', () => loadEvents(true));
  $('#csvPseudonymous').on('click', () => Kit.download('/api/admin/activity.csv?' + filters().toString()));
  $('#csvNamed').on('click', () => {
    const query = filters();
    query.set('names', '1');
    Kit.download('/api/admin/activity.csv?' + query.toString());
  });

  const today = new Date();
  $('#filterTo').val(isoDay(today));
  $('#filterFrom').val(isoDay(new Date(today.getTime() - 6 * 86400000)));
  loadPeople();
  loadEvents(false);
})();
