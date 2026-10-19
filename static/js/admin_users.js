(function () {
  let users = [];

  function load() {
    return Kit.api('/api/users').then(data => {
      users = data.users;
      $('#userRows').html(users.map(user => `
        <tr>
          <td>${Kit.escape(user.username)}</td>
          <td>${Kit.escape(user.email)}</td>
          <td><span class="badge text-bg-${user.role === 'admin' ? 'danger' : 'secondary'}">${Kit.escape(user.role)}</span></td>
          <td>${Kit.escape(user.kit_role)}${user.disabled ? ' <span class="badge text-bg-dark">switched off</span>' : ''}</td>
          <td>${Kit.tags(user.groups)}</td>
          <td class="small text-muted">${Kit.escape(user.last_login || '-')}</td>
          <td class="text-end text-nowrap">
            <button class="btn btn-outline-primary btn-sm edit-user" data-id="${user.id}" aria-label="Edit ${Kit.escape(user.username)}"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-outline-secondary btn-sm toggle-user" data-id="${user.id}">${user.disabled ? 'Switch on' : 'Switch off'}</button>
            <button class="btn btn-outline-danger btn-sm delete-user" data-id="${user.id}" aria-label="Delete ${Kit.escape(user.username)}"><i class="bi bi-trash" aria-hidden="true"></i></button>
          </td>
        </tr>`).join(''));
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  function resetForm() {
    const form = $('#userForm')[0];
    form.reset();
    form.elements.id.value = '';
    $('#userFormTitle').html('<i class="bi bi-person-plus"></i> New user');
  }

  $('#userRows').on('click', '.edit-user', function () {
    const user = users.find(item => item.id === $(this).data('id'));
    if (!user) return;
    const form = $('#userForm')[0];
    form.elements.id.value = user.id;
    form.elements.username.value = user.username;
    form.elements.email.value = user.email;
    form.elements.password.value = '';
    form.elements.role.value = user.role;
    form.elements.kit_role.value = user.kit_role;
    form.elements.groups.value = user.groups.join(', ');
    $('#userFormTitle').html('<i class="bi bi-pencil"></i> Edit ' + Kit.escape(user.username));
  });

  $('#userRows').on('click', '.delete-user', function () {
    const user = users.find(item => item.id === $(this).data('id'));
    if (!user || !window.confirm('Delete ' + user.username + '? Their projects stay, visible to admins only.')) return;
    Kit.api('/api/users/' + user.id, { method: 'DELETE' }).then(() => { Kit.toast('User deleted', 'success'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  // Deprovisioning (ADR-0016): switched off = no sign-in, sessions end, tokens revoked; items stay.
  $('#userRows').on('click', '.toggle-user', function () {
    const user = users.find(item => item.id === $(this).data('id'));
    if (!user) return;
    if (!user.disabled && !window.confirm('Switch off ' + user.username + '? They are signed out and their API tokens are revoked. Their projects stay.')) return;
    Kit.api('/api/users/' + user.id + (user.disabled ? '/reactivate' : '/deactivate'), { method: 'POST', body: {} })
      .then(() => { Kit.toast(user.disabled ? 'Account switched on' : 'Account switched off', 'success'); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#resetUserForm').on('click', event => { event.preventDefault(); resetForm(); });

  $('#userForm').on('submit', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    const body = {
      username: form.get('username'),
      email: form.get('email'),
      role: form.get('role'),
      kit_role: form.get('kit_role'),
      groups: String(form.get('groups') || '').split(',').map(group => group.trim()).filter(Boolean)
    };
    if (form.get('password')) body.password = form.get('password');
    const id = form.get('id');
    Kit.api(id ? '/api/users/' + id : '/api/users', { method: id ? 'PUT' : 'POST', body })
      .then(() => { Kit.toast('User saved', 'success'); resetForm(); load(); })
      .catch(err => Kit.toast(err.message, 'danger'));
  });

  $('#syncNow').on('click', () => {
    $('#syncResult').removeClass('d-none').text('Syncing...');
    Kit.api('/api/sso/sync', { method: 'POST', body: {} })
      .then(result => { $('#syncResult').text(JSON.stringify(result, null, 2)); $('#ssoPending').text('0'); load(); })
      .catch(err => { $('#syncResult').text(err.message); Kit.toast(err.message, 'danger'); });
  });

  load();
})();
