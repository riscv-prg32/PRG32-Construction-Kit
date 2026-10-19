// The Classes page (ADR-0016): teachers make classes and add students; teachers and
// facilitators see their students' projects (read-only); students see their classes.
(function () {
  'use strict';

  function card(item) {
    const manage = item.my_role === 'teacher' || window.kitIsAdmin;
    const members = item.members ? item.members.map(member => `
      <li class="d-flex justify-content-between align-items-center">
        <span>${Kit.escape(member.username)} <span class="badge text-bg-light">${Kit.escape(member.role)}</span></span>
        ${manage && (member.role === 'student' || window.kitIsAdmin) ? `<button class="btn btn-link btn-sm text-danger p-0 remove-member"
          data-class="${item.id}" data-user="${member.user_id}" aria-label="Remove ${Kit.escape(member.username)}">remove</button>` : ''}
      </li>`).join('') : '';
    return `<div class="col-lg-6"><div class="card shadow-sm h-100"><div class="card-header d-flex justify-content-between">
        <strong>${Kit.escape(item.name)}</strong><span class="small text-muted">you: ${Kit.escape(item.my_role || 'admin')}</span></div>
      <div class="card-body">
        ${item.members ? `<ul class="list-unstyled small mb-2">${members}</ul>` : ''}
        ${manage ? `<form class="d-flex gap-1 mb-2 add-member" data-class="${item.id}">
          <label class="visually-hidden" for="add-${item.id}">Add a student by username or email</label>
          <input class="form-control form-control-sm" id="add-${item.id}" name="username" placeholder="Add a student (username or email)">
          ${window.kitIsAdmin ? `<select class="form-select form-select-sm w-auto" name="role" aria-label="As">
            <option>student</option><option>teacher</option><option>facilitator</option></select>` : ''}
          <button class="btn btn-outline-primary btn-sm">Add</button></form>` : ''}
        ${item.members ? `<button class="btn btn-outline-secondary btn-sm show-projects" data-class="${item.id}">Students' projects</button>
          <ul class="small mt-2 mb-0" id="projects-${item.id}"></ul>` : ''}
      </div></div></div>`;
  }

  function load() {
    return Kit.api('/api/classes').then(data => {
      $('#classCards').html(data.classes.map(card).join('') || '<div class="col text-muted">You are not in a class yet.</div>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  }

  $('#classForm').on('submit', function (event) {
    event.preventDefault();
    Kit.api('/api/classes', { method: 'POST', body: { name: new FormData(this).get('name') } })
      .then(() => { this.reset(); load(); }).catch(err => Kit.toast(err.message, 'danger'));
  });
  $('#classCards').on('submit', '.add-member', function (event) {
    event.preventDefault();
    const form = new FormData(this);
    Kit.api(`/api/classes/${$(this).data('class')}/members`, { method: 'POST',
      body: { username: form.get('username'), role: form.get('role') || 'student' } })
      .then(load).catch(err => Kit.toast(err.message, 'danger'));
  }).on('click', '.remove-member', function () {
    Kit.api(`/api/classes/${$(this).data('class')}/members/${$(this).data('user')}`, { method: 'DELETE' })
      .then(load).catch(err => Kit.toast(err.message, 'danger'));
  }).on('click', '.show-projects', function () {
    const id = $(this).data('class');
    Kit.api(`/api/classes/${id}/projects`).then(data => {
      $(`#projects-${id}`).html(data.projects.map(project => `<li><a href="/projects/${encodeURIComponent(project.id)}">${Kit.escape(project.title)}</a>
        <span class="text-muted">(read-only)</span></li>`).join('') || '<li class="text-muted">No projects yet.</li>');
    }).catch(err => Kit.toast(err.message, 'danger'));
  });

  window.kitIsAdmin = document.body.dataset.admin === '1';
  load();
})();
